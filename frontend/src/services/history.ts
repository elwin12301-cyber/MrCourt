import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { api } from './api';
import type { AssistantReply, Step } from './assistant';
import type { Answer, InputMethod } from './questions';

export type OutcomeLabel = 'Answered' | 'No information found' | 'Saved';

export interface HistoryItem {
  id: string;
  text: string;
  created_at: string;
  input_method: InputMethod;
  mode: 'answer' | 'assistant' | 'text';
  outcome_label: OutcomeLabel;
}

export interface HistoryPage {
  items: HistoryItem[];
  next_before: string | null;
}

export interface HistoryDetail extends HistoryItem {
  outcome: Answer['outcome'];
  answer_mode: 'full' | 'passages';
  steps: Step[] | null;
  paragraphs: Answer['paragraphs'];
  citations: Answer['citations'];
  message: string | null;
  disclaimer: string;
  lawyer_reminder: string | null;
  /** Text Assistant entries: the conversation as it was, even if deleted since. */
  lines: { id: string; text: string; source: 'voice' | 'typed'; created_at: string }[] | null;
  conversation_id: string | null;
  conversation_deleted: boolean;
}

export interface HistoryFilters {
  q: string;
  outcome: '' | 'answered' | 'none';
  input: '' | 'typed' | 'voice';
  source: '' | 'ask' | 'text';
}

export interface WorkspaceItem extends HistoryItem {
  asker_id: string;
  asker_name: string;
  asker_role: 'advocate' | 'petitioner' | 'admin';
}

export interface WorkspacePage {
  items: WorkspaceItem[];
  next_before: string | null;
}

function params(filters: HistoryFilters, pageParam: string) {
  const out = new URLSearchParams();
  if (filters.q.trim()) out.set('q', filters.q.trim());
  if (filters.outcome) out.set('outcome', filters.outcome);
  if (filters.input) out.set('input', filters.input);
  if (filters.source) out.set('source', filters.source);
  if (pageParam) out.set('before', pageParam);
  return out;
}

/** Everyone's questions (administrators only). Showing the list is recorded in the audit log, so it only runs when asked for. */
export function useWorkspaceHistory(filters: HistoryFilters, enabled: boolean) {
  return useInfiniteQuery({
    queryKey: ['history', 'workspace', filters],
    enabled,
    initialPageParam: '',
    staleTime: Infinity,
    gcTime: 3000,
    refetchOnWindowFocus: false,
    queryFn: ({ pageParam }): Promise<WorkspacePage> => api.get<WorkspacePage>(`/admin/questions?${params(filters, pageParam)}`),
    getNextPageParam: (last: WorkspacePage) => last.next_before ?? undefined,
  });
}

export function useHistory(filters: HistoryFilters, enabled = true) {
  return useInfiniteQuery({
    enabled,
    queryKey: ['history', filters],
    initialPageParam: '',
    placeholderData: (previous) => previous,
    queryFn: ({ pageParam }): Promise<HistoryPage> => api.get<HistoryPage>(`/history?${params(filters, pageParam)}`),
    getNextPageParam: (last: HistoryPage) => last.next_before ?? undefined,
  });
}

export function useHistoryDetail(id: string | null) {
  return useQuery({
    queryKey: ['history', 'detail', id],
    enabled: id !== null,
    queryFn: () => api.get<HistoryDetail>(`/history/${id}`),
  });
}

/** A stored question and answer, shaped like a fresh reply so the same message component shows it. */
export function asReply(d: HistoryDetail): Answer | AssistantReply {
  const base: Answer = {
    question_id: d.id,
    answer_mode: d.answer_mode,
    outcome: d.outcome,
    paragraphs: d.paragraphs,
    citations: d.citations,
    message: d.message,
    disclaimer: d.disclaimer,
    lawyer_reminder: d.lawyer_reminder,
  };
  return d.steps ? { ...base, steps: d.steps, proposed_action: null } : base;
}
