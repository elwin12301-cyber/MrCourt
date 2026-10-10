import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './api';

export type DocumentKind = 'act_section' | 'judgment' | 'note';
export type DocumentStatus = 'processing' | 'ready' | 'failed';

export interface KnowledgeDocument {
  id: string;
  title: string;
  citation: string;
  kind: DocumentKind;
  scope: 'shared' | 'private';
  status: DocumentStatus;
  status_reason: string | null;
  passage_count: number | null;
  page_count: number | null;
  ocr_pages: number | null;
  created_at: string;
  can_remove: boolean;
}

export const KIND_LABEL: Record<DocumentKind, string> = {
  act_section: 'Act or section',
  judgment: 'Judgment',
  note: 'Private note',
};

export const STATUS_LABEL: Record<DocumentStatus, string> = {
  processing: 'Processing',
  ready: 'Ready',
  failed: 'Failed',
};

const KEY = ['knowledge'] as const;

/** The list refreshes by itself while anything is still processing. */
export function useDocuments(search: string) {
  return useQuery({
    queryKey: [...KEY, search],
    queryFn: () => api.get<KnowledgeDocument[]>(`/knowledge/documents${search ? `?q=${encodeURIComponent(search)}` : ''}`),
    refetchInterval: (query) => (query.state.data?.some((d) => d.status === 'processing') ? 1500 : false),
  });
}

export interface NewDocument {
  title: string;
  citation: string;
  kind?: DocumentKind;
  text?: string;
  file?: File | null;
}

export function useAddDocument() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (doc: NewDocument) => {
      const form = new FormData();
      form.set('title', doc.title);
      form.set('citation', doc.citation);
      if (doc.kind) form.set('kind', doc.kind);
      if (doc.file) form.set('file', doc.file);
      else form.set('text', doc.text ?? '');
      return api.post<KnowledgeDocument>('/knowledge/documents', form);
    },
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}

export function useRemoveDocument() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/knowledge/documents/${id}`),
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}
