import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './api';

export type ClientStatus = 'notice_stage' | 'hearing_scheduled' | 'awaiting_order' | 'closed';

export const CLIENT_STATUS_LABEL: Record<ClientStatus, string> = {
  notice_stage: 'Notice stage',
  hearing_scheduled: 'Hearing scheduled',
  awaiting_order: 'Awaiting order',
  closed: 'Closed',
};

/** The statuses an advocate can choose from, in the order they are offered. */
export const CLIENT_STATUS_OPTIONS: ClientStatus[] = [
  'notice_stage',
  'hearing_scheduled',
  'awaiting_order',
  'closed',
];

export interface Lawyer {
  name: string;
  verification_status: 'none' | 'pending' | 'verified';
  phone: string | null;
  email: string | null;
  office: string | null;
  available: boolean;
}

export interface HearingDescription {
  text: string;
  label: string;
  disclaimer: string;
}

export interface HearingForClient {
  id: string;
  scheduled_at: string;
  court: string;
  description: HearingDescription | null;
  outcome: string | null;
}

export interface TimelineEntry {
  id: string;
  kind: string;
  text: string;
  occurred_at: string;
}

export interface ClientDocument {
  id: string;
  file_name: string;
  size_bytes: number;
}

export interface ClientCaseSummary {
  id: string;
  title: string;
  court: string;
  status: ClientStatus | null;
  status_changed_at: string | null;
  next_hearing: HearingForClient | null;
  lawyer: Lawyer;
}

export interface ClientCase extends ClientCaseSummary {
  hearings: HearingForClient[];
  timeline: TimelineEntry[];
  documents: ClientDocument[];
  access: { advocate_name: string; since: string | null; other_people_with_access: number };
}

export interface ClientUpdate {
  id: string;
  case_id: string;
  kind: string;
  message: string;
  created_at: string;
  read: boolean;
}

export interface ClientDashboard {
  cases: ClientCaseSummary[];
  unread_updates: number;
  latest_updates: ClientUpdate[];
}

export interface GlossaryTerm {
  term: string;
  meaning: string;
}

export const CLIENT_DASHBOARD_KEY = ['client', 'dashboard'] as const;

export function useClientDashboard() {
  return useQuery({
    queryKey: CLIENT_DASHBOARD_KEY,
    queryFn: () => api.get<ClientDashboard>('/client/dashboard'),
  });
}

export function useClientCase(caseId: string | undefined) {
  return useQuery({
    queryKey: ['client', 'case', caseId],
    enabled: !!caseId,
    retry: false,
    queryFn: () => api.get<ClientCase>(`/client/cases/${caseId}`),
  });
}

export function useGlossary() {
  return useQuery({
    queryKey: ['glossary'],
    staleTime: Infinity,
    queryFn: () => api.get<GlossaryTerm[]>('/glossary'),
  });
}

export interface ClientQuestion {
  id: string;
  kind: 'question' | 'update_request';
  text: string;
  sent_at: string;
  reply_text: string | null;
  replied_at: string | null;
  reply_read: boolean;
}

export const questionsKey = (caseId: string) => ['client', 'case', caseId, 'questions'] as const;

export function useMyQuestions(caseId: string) {
  return useQuery({
    queryKey: questionsKey(caseId),
    queryFn: () => api.get<ClientQuestion[]>(`/client/cases/${caseId}/questions`),
  });
}

export const askLawyer = (caseId: string, kind: ClientQuestion['kind'], text?: string) =>
  api.post<ClientQuestion>(`/client/cases/${caseId}/questions`, { kind, text });

export const markReplyRead = (questionId: string) => api.post<void>(`/client/questions/${questionId}/read`);

/** How often a signed-in client's unread count is refreshed. Tests shorten it. */
export const UPDATES_POLL_MS = Number(import.meta.env.VITE_UPDATES_POLL_MS ?? 30_000);

export interface UpdatesResponse {
  unread_count: number;
  items: ClientUpdate[];
}

export const UPDATES_KEY = ['client', 'updates'] as const;

/**
 * The client's updates. Refreshed every 30 seconds and whenever the window regains focus, so a
 * change the advocate makes shows up within a minute without reloading (SC-004).
 */
export function useClientUpdates(enabled: boolean) {
  return useQuery({
    queryKey: UPDATES_KEY,
    enabled,
    queryFn: () => api.get<UpdatesResponse>('/client/updates'),
    refetchInterval: UPDATES_POLL_MS,
    refetchOnWindowFocus: true,
    staleTime: 0,
  });
}

export function useMarkUpdatesRead() {
  const client = useQueryClient();
  const refresh = () => {
    void client.invalidateQueries({ queryKey: UPDATES_KEY });
    void client.invalidateQueries({ queryKey: CLIENT_DASHBOARD_KEY });
  };
  return {
    one: useMutation({ mutationFn: (id: string) => api.post<void>(`/client/updates/${id}/read`), onSuccess: refresh }),
    all: useMutation({ mutationFn: () => api.post<void>('/client/updates/read-all'), onSuccess: refresh }),
  };
}
