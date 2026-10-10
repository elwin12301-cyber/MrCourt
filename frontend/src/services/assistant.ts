import { useQuery } from '@tanstack/react-query';
import { api } from './api';
import type { Answer, InputMethod } from './questions';

export interface AssistantStatus {
  answers: 'full' | 'passages';
  assistant: boolean;
  notice: string | null;
  /** Whether meaning-based search is set up (otherwise keyword search only). */
  search: 'meaning' | 'keywords';
  /** Server-side speech to text is set up. */
  speech: boolean;
  /** Scanned documents can be read. */
  ocr: boolean;
}

export function useAssistantStatus() {
  return useQuery({
    queryKey: ['assistant-status'],
    queryFn: () => api.get<AssistantStatus>('/assistant/status'),
    staleTime: 60_000,
  });
}

export interface Step {
  tool: string;
  label: string;
  status: 'ok' | 'refused' | 'failed';
  detail: string | null;
}

export interface ProposedAction {
  id: string;
  kind: string;
  summary: string;
  expires_at: string;
}

/** What the assistant returns: an answer plus the steps it took and anything it proposes. */
export interface AssistantReply extends Answer {
  steps: Step[];
  proposed_action: ProposedAction | null;
}

export const runAssistant = (text: string, inputMethod: InputMethod = 'typed') =>
  api.post<AssistantReply>('/assistant/requests', { text, input_method: inputMethod });

export const confirmAction = (id: string) =>
  api.post<{ status: 'done'; draft_id: string }>(`/assistant/actions/${id}/confirm`);

export const declineAction = (id: string) => api.post<{ status: 'declined' }>(`/assistant/actions/${id}/decline`);

/** Starter requests for assistant mode. */
export const ASSISTANT_SUGGESTIONS = {
  advocate: [
    { label: 'My hearings this month', question: 'What hearings do I have in the next 30 days?' },
    { label: 'Prepare a notice', question: 'Prepare a legal notice draft for my first case.' },
  ],
  petitioner: [
    { label: 'Status of my cases', question: 'What is the status of my cases?' },
    { label: 'My next hearing', question: 'When is my next hearing?' },
  ],
} as const;
