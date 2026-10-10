import { useQuery } from '@tanstack/react-query';
import { api } from './api';

export interface Passage {
  id: string;
  text: string;
  citation: string;
  document_title: string | null;
  page: number | null;
  read_by_ocr: boolean;
  ocr_confidence: number | null;
  scope: 'shared' | 'private';
}

export function usePassage(id: string | null | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ['passage', id],
    enabled: enabled && !!id,
    retry: false,
    queryFn: () => api.get<Passage>(`/knowledge/passages/${id}`),
  });
}
