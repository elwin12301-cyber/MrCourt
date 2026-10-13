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
  /** Whose private document it is: sent to administrators only. */
  owner?: string | null;
  /** Mapped details (feature 008), when the document has been mapped. */
  details: DetailsSummary | null;
}

export interface DetailsSummary {
  doc_type: string | null;
  court: string | null;
  case_number: string | null;
  decided_on: string | null;
  language: string | null;
  text_quality: 'readable' | 'unreadable' | null;
  short: string | null;
}

/** Filters by document details; empty values are left out. */
export interface SourceFilterValues {
  type?: string;
  court?: string;
  year?: string;
  act?: string;
  section?: string;
  case?: string;
}

export interface FilterOptions {
  types: string[];
  courts: string[];
  years: number[];
  acts: string[];
}

export type Confidence = 'found' | 'likely' | 'not_found' | 'confirmed';

export interface DetailField {
  value: unknown;
  confidence: Confidence;
  source: 'text' | 'person';
  alternatives?: unknown[];
}

export interface DocumentDetails {
  document_id: string;
  can_edit: boolean;
  text_quality: string | null;
  fields: Record<string, DetailField>;
}

export interface RemapSummary {
  documents: number;
  fields_found: Record<string, number>;
  unreadable: number;
}

export const DOC_TYPES = ['statute', 'judgment', 'order', 'petition', 'deed', 'deposition', 'notice', 'other'] as const;
export const OUTCOMES = ['allowed', 'dismissed', 'partly allowed', 'decreed', 'disposed'] as const;

export const TYPE_LABEL: Record<string, string> = {
  statute: 'Statute',
  judgment: 'Judgment',
  order: 'Order',
  petition: 'Petition',
  deed: 'Deed',
  deposition: 'Deposition',
  notice: 'Notice',
  other: 'Other',
};

export const ACT_LABEL: Record<string, string> = {
  IPC: 'Indian Penal Code',
  BNS: 'Bharatiya Nyaya Sanhita',
  BNSS: 'Bharatiya Nagarik Suraksha Sanhita',
  BSA: 'Bharatiya Sakshya Adhiniyam',
  CRPC: 'Code of Criminal Procedure',
  CPC: 'Code of Civil Procedure',
  NI: 'Negotiable Instruments Act',
  CONSTITUTION: 'Constitution of India',
  CONTRACT: 'Indian Contract Act',
  TPA: 'Transfer of Property Act',
  EVIDENCE: 'Evidence Act',
};

export function filterQuery(filters: SourceFilterValues): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) if (value) params.set(key, value);
  return params.toString();
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
export function useDocuments(search: string, filters: SourceFilterValues = {}) {
  const query = filterQuery({ ...filters, ...(search ? { q: search } : {}) } as SourceFilterValues);
  return useQuery({
    queryKey: [...KEY, search, filters],
    queryFn: () => api.get<KnowledgeDocument[]>(`/knowledge/documents${query ? `?${query}` : ''}`),
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

export function useFilterOptions() {
  return useQuery({ queryKey: [...KEY, 'filters'], queryFn: () => api.get<FilterOptions>('/knowledge/documents/filters') });
}

export function useDocumentDetails(id: string) {
  return useQuery({ queryKey: [...KEY, 'details', id], queryFn: () => api.get<DocumentDetails>(`/knowledge/documents/${id}/details`) });
}

export function useSaveDetails(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (fields: Record<string, unknown>) =>
      api.patch<DocumentDetails>(`/knowledge/documents/${id}/details`, { fields }),
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}

export function useRemap() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<RemapSummary>('/knowledge/documents/remap'),
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}
