import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './api';
import type { KnowledgeDocument } from './knowledge';

export interface Line {
  id: string;
  text: string;
  source: 'voice' | 'typed';
  created_at: string;
}

export interface ConversationRow {
  id: string;
  title: string;
  language: string;
  updated_at: string;
  line_count: number;
}

export interface Conversation extends ConversationRow {
  lines: Line[];
}

const KEY = ['text'] as const;

export function useConversations() {
  return useQuery({ queryKey: [...KEY, 'list'], queryFn: () => api.get<ConversationRow[]>('/text/conversations') });
}

export function useConversation(id: string | null) {
  return useQuery({
    queryKey: [...KEY, 'one', id],
    enabled: id !== null,
    retry: false,
    queryFn: () => api.get<Conversation>(`/text/conversations/${id}`),
  });
}

function useChange<TVars, TResult>(run: (vars: TVars) => Promise<TResult>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: KEY });
      void client.invalidateQueries({ queryKey: ['history'] }); // a conversation has a History entry
    },
  });
}

export const useCreateConversation = () =>
  useChange((language: string) => api.post<Conversation>('/text/conversations', { language }));

export const useUpdateConversation = () =>
  useChange(({ id, ...patch }: { id: string; title?: string; language?: string }) =>
    api.patch<Conversation>(`/text/conversations/${id}`, patch),
  );

export const useDeleteConversation = () => useChange((id: string) => api.delete<void>(`/text/conversations/${id}`));

export const useAddLine = () =>
  useChange(({ id, text, source }: { id: string; text: string; source: 'voice' | 'typed' }) =>
    api.post<Line>(`/text/conversations/${id}/lines`, { text, source }),
  );

export const useEditLine = () =>
  useChange(({ id, lineId, text }: { id: string; lineId: string; text: string }) =>
    api.patch<Line>(`/text/conversations/${id}/lines/${lineId}`, { text }),
  );

export const useRemoveLine = () =>
  useChange(({ id, lineId }: { id: string; lineId: string }) => api.delete<void>(`/text/conversations/${id}/lines/${lineId}`));

export const useAddToKnowledge = () =>
  useChange(({ id, citation }: { id: string; citation?: string }) =>
    api.post<KnowledgeDocument>(`/text/conversations/${id}/knowledge`, { citation }),
  );

export const pdfUrl = (id: string) => `/api/v1/text/conversations/${id}/pdf`;

/** One spoken turn, sent to the speech service through MrCourt. The audio is not stored. */
export async function transcribe(wav: Blob, language: string): Promise<string> {
  const form = new FormData();
  form.set('audio', wav, 'turn.wav');
  form.set('language', language);
  return (await api.post<{ text: string }>('/speech/transcribe', form)).text;
}
