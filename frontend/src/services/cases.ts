import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './api';
import type { ClientStatus } from './client';

export type CaseStatus = 'active' | 'hearing_soon' | 'closed';

export interface CaseSummary {
  id: string;
  title: string;
  cnr_number: string;
  court: string;
  status: CaseStatus;
  next_hearing_at: string | null;
}

export interface Party {
  side: 'petitioner' | 'respondent';
  name: string;
  is_client: boolean;
}

export interface Hearing {
  id: string;
  scheduled_at: string;
  court_room: string | null;
  purpose: string | null;
  outcome: string | null;
  outcome_shared: boolean;
}

export interface CaseDocument {
  id: string;
  file_name: string;
  size_bytes: number;
  shared_with_client: boolean;
}

export interface CaseDetail extends CaseSummary {
  stage: string | null;
  court_room: string | null;
  parties: Party[];
  documents: CaseDocument[];
  hearings: Hearing[];
  notes: string | null;
  client_status: ClientStatus | null;
  client_status_changed_at: string | null;
}

export interface Dashboard {
  active_cases: number;
  hearings_this_week: number;
  drafts_to_review: number;
  upcoming_hearings: CaseSummary[];
  recent_activity: { message: string; created_at: string }[];
}

export interface Invitation {
  id: string;
  case_id: string;
  case_title: string;
  status: string;
}

export const STATUS_LABEL: Record<CaseStatus, string> = {
  active: 'Active',
  hearing_soon: 'Hearing soon',
  closed: 'Closed',
};

export const STATUS_TONE: Record<CaseStatus, 'active' | 'soon' | 'closed'> = {
  active: 'active',
  hearing_soon: 'soon',
  closed: 'closed',
};

export function useDashboard() {
  return useQuery({ queryKey: ['dashboard'], queryFn: () => api.get<Dashboard>('/dashboard') });
}

export function useCases(q: string, status: CaseStatus | 'all') {
  const params = new URLSearchParams();
  if (q.trim()) params.set('q', q.trim());
  if (status !== 'all') params.set('status', status);
  const qs = params.toString();
  return useQuery({
    queryKey: ['cases', q.trim(), status],
    queryFn: () => api.get<CaseSummary[]>(`/cases${qs ? `?${qs}` : ''}`),
    placeholderData: (previous) => previous,
  });
}

export function useCase(caseId: string | undefined) {
  return useQuery({
    queryKey: ['case', caseId],
    enabled: !!caseId,
    queryFn: () => api.get<CaseDetail>(`/cases/${caseId}`),
    retry: false,
  });
}

export function useInvitations() {
  return useQuery({ queryKey: ['invitations'], queryFn: () => api.get<Invitation[]>('/invitations') });
}

/** Runs a mutation, then refreshes everything that depends on case data. */
export function useCaseMutation<TInput, TResult = unknown>(fn: (input: TInput) => Promise<TResult>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['cases'] });
      void client.invalidateQueries({ queryKey: ['case'] });
      void client.invalidateQueries({ queryKey: ['dashboard'] });
      void client.invalidateQueries({ queryKey: ['invitations'] });
    },
  });
}

export interface NewCase {
  title: string;
  cnr_number: string;
  court: string;
  stage?: string;
  parties: Party[];
}

export const createCase = (input: NewCase) => api.post<CaseDetail>('/cases', input);
export const patchCase = (id: string, input: Partial<CaseDetail> & { court_room?: string }) =>
  api.patch<CaseDetail>(`/cases/${id}`, input);
export const addHearing = (id: string, input: { scheduled_at: string; purpose?: string; court_room?: string }) =>
  api.post<Hearing>(`/cases/${id}/hearings`, input);
export const rescheduleHearing = (id: string, hearingId: string, scheduled_at: string) =>
  api.patch<Hearing>(`/cases/${id}/hearings/${hearingId}`, { scheduled_at });
export const uploadDocument = (id: string, file: File) => {
  const form = new FormData();
  form.append('file', file);
  return api.post<CaseDocument>(`/cases/${id}/documents`, form);
};
export const inviteToCase = (id: string, contact: string) =>
  api.post<Invitation>(`/cases/${id}/invitations`, { contact });
export const acceptInvitation = (id: string) => api.post<Invitation>(`/invitations/${id}/accept`);

// Formatting shared by the screens, matching the prototype's wording.
export function dateParts(iso: string): { day: string; month: string } {
  const d = new Date(iso);
  return {
    day: String(d.getDate()).padStart(2, '0'),
    month: new Intl.DateTimeFormat('en-IN', { month: 'short' }).format(d).toUpperCase(),
  };
}

export function timeOf(iso: string): string {
  return new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit', hour12: true }).format(
    new Date(iso),
  );
}

export function dayOf(iso: string): string {
  return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }).format(
    new Date(iso),
  );
}

export function dateTimeOf(iso: string): string {
  return `${dayOf(iso)}, ${timeOf(iso)}`;
}

export function timeAgo(iso: string, now: Date = new Date()): string {
  const minutes = Math.max(0, Math.round((now.getTime() - new Date(iso).getTime()) / 60000));
  if (minutes < 60) return minutes <= 1 ? 'Just now' : `${minutes} minutes ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`;
  const days = Math.round(hours / 24);
  return days === 1 ? 'Yesterday' : `${days} days ago`;
}

export function fileSize(bytes: number): string {
  if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1000))} KB`;
}
