import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './api';

export interface AuditItem {
  id: string;
  admin_name: string;
  action: string;
  action_label: string;
  target_type: string;
  target_id: string | null;
  target_name: string | null;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface Overview {
  advocates: number;
  clients: number;
  open_cases: number;
  pending_verifications: number;
  suspended_accounts: number;
  recent_audit: AuditItem[];
}

export type PersonStatus = 'active' | 'suspended' | 'deactivated';
export type StatusFilter = 'all' | PersonStatus | 'pending';

export interface UserRow {
  id: string;
  role: 'advocate' | 'petitioner';
  full_name: string;
  email: string | null;
  phone: string | null;
  status: PersonStatus;
  verification_status: 'none' | 'pending' | 'verified';
  bar_registration_number: string | null;
  created_at: string;
  case_count: number;
}

export interface UserDetail extends UserRow {
  cases: { id: string; title: string; status: string; relation: 'advocate' | 'client'; advocate_name: string }[];
  suspension: { reason: string; at: string; by: string } | null;
}

export interface CaseRow {
  id: string;
  title: string;
  court: string;
  status: string;
  advocate_name: string;
  client_count: number;
  next_hearing_at: string | null;
}

export interface CaseFull {
  id: string;
  title: string;
  cnr_number: string;
  court: string;
  status: string;
  stage: string | null;
  court_room: string | null;
  notes: string | null;
  client_status: string | null;
  client_status_changed_at: string | null;
  advocate: { id: string; name: string };
  parties: { side: string; name: string; is_client: boolean }[];
  hearings: { id: string; scheduled_at: string; purpose: string | null; court_room: string | null; outcome: string | null; outcome_shared: boolean }[];
  documents: { id: string; file_name: string; size_bytes: number; shared_with_client: boolean }[];
  timeline: { id: string; kind: string; text: string; shared_with_client: boolean; occurred_at: string }[];
  clients: { id: string; name: string; status: string; accepted_at: string | null }[];
  client_questions: { id: string; client_name: string; kind: string; text: string; sent_at: string; reply_text: string | null; replied_at: string | null }[];
}

export interface AuditPage {
  items: AuditItem[];
  next_before: string | null;
}

export const ADMIN_KEY = ['admin'] as const;

export function useOverview() {
  return useQuery({ queryKey: [...ADMIN_KEY, 'overview'], queryFn: () => api.get<Overview>('/admin/overview') });
}

export function usePeople(role: 'advocate' | 'petitioner', q: string, status: StatusFilter) {
  const params = new URLSearchParams({ role });
  if (q.trim()) params.set('q', q.trim());
  if (status !== 'all') params.set('status', status);
  return useQuery({
    queryKey: [...ADMIN_KEY, 'people', role, q.trim(), status],
    queryFn: () => api.get<UserRow[]>(`/admin/users?${params}`),
    placeholderData: (previous) => previous,
  });
}

export function usePerson(userId: string | undefined) {
  return useQuery({
    queryKey: [...ADMIN_KEY, 'person', userId],
    enabled: !!userId,
    retry: false,
    // Opening a person's page is recorded in the audit log, so never refetch it in the background.
    // The copy is kept for a few seconds only: long enough that React's double mount in development
    // does not log a visit twice, short enough that coming back later is logged again.
    staleTime: Infinity,
    gcTime: 3000,
    refetchOnWindowFocus: false,
    queryFn: () => api.get<UserDetail>(`/admin/users/${userId}`),
  });
}

export function useAdminCases(q: string) {
  const qs = q.trim() ? `?q=${encodeURIComponent(q.trim())}` : '';
  return useQuery({
    queryKey: [...ADMIN_KEY, 'cases', q.trim()],
    queryFn: () => api.get<CaseRow[]>(`/admin/cases${qs}`),
    placeholderData: (previous) => previous,
  });
}

export function useCaseInFull(caseId: string | undefined) {
  return useQuery({
    queryKey: [...ADMIN_KEY, 'case', caseId],
    enabled: !!caseId,
    retry: false,
    // Each load of the full case is recorded in the audit log, so it is loaded once per visit.
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    gcTime: 3000, // see usePerson: one visit is one audit entry
    queryFn: () => api.get<CaseFull>(`/admin/cases/${caseId}`),
  });
}

export function useAuditLog(before: string | null) {
  const qs = before ? `?before=${encodeURIComponent(before)}` : '';
  return useQuery({
    queryKey: [...ADMIN_KEY, 'audit', before],
    queryFn: () => api.get<AuditPage>(`/admin/audit${qs}`),
  });
}

/** Runs an account change, then refreshes everything the admin screens show. */
export function useAdminAction<T, R = unknown>(fn: (input: T) => Promise<R>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    // Refresh the lists. The person's page and the full case are never reloaded in the background,
    // because loading them is recorded in the audit log.
    onSuccess: () =>
      Promise.all(
        ['people', 'overview', 'audit', 'cases'].map((key) => client.invalidateQueries({ queryKey: [...ADMIN_KEY, key] })),
      ),
  });
}

export const editPerson = (id: string, patch: Partial<Pick<UserRow, 'full_name' | 'email' | 'phone' | 'bar_registration_number'>>) =>
  api.patch<UserRow>(`/admin/users/${id}`, patch);
export const suspendPerson = (id: string, reason: string) => api.post<UserRow>(`/admin/users/${id}/suspend`, { reason });
export const reactivatePerson = (id: string) => api.post<UserRow>(`/admin/users/${id}/reactivate`);
export const signPersonOut = (id: string) => api.post<void>(`/admin/users/${id}/sign-out`);
export const decideVerification = (id: string, decision: 'verified' | 'rejected') =>
  api.post(`/admin/verifications/${id}`, { decision });

/** Plain-language summary of an audit entry's details. */
export function describeDetail(item: AuditItem): string {
  const d = item.detail;
  if (typeof d.reason === 'string') return `Reason: ${d.reason}`;
  if (Array.isArray(d.fields)) return `Changed: ${(d.fields as string[]).map((f) => f.replace(/_/g, ' ')).join(', ')}`;
  if (typeof d.file_name === 'string') return String(d.file_name);
  return '';
}

export interface PersonQuestion {
  id: string;
  text: string;
  created_at: string;
  input_method: 'typed' | 'voice';
  mode: 'answer' | 'assistant';
  outcome_label: 'Answered' | 'No information found';
}

/** Opening a person's question list is recorded in the audit log, so it only runs when asked for. */
export function usePersonQuestions(userId: string, enabled: boolean) {
  return useQuery({
    queryKey: [...ADMIN_KEY, 'questions', userId],
    enabled,
    retry: false,
    staleTime: Infinity,
    gcTime: 3000,
    refetchOnWindowFocus: false,
    queryFn: () => api.get<{ items: PersonQuestion[]; next_before: string | null }>(`/admin/users/${userId}/questions?limit=50`),
  });
}
