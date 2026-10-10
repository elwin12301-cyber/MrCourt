import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, api } from './api';

export type TemplateKey = 'notice' | 'bail' | 'reply' | 'affidavit';

export interface Draft {
  id: string;
  case_id: string | null;
  template: TemplateKey;
  title: string;
  subtitle: string;
  body: string;
  version: number;
  ai_generated: boolean;
  reviewed: boolean;
  last_edited_at: string;
}

export const TEMPLATES: { key: TemplateKey; label: string; icon: 'file' | 'gavel' | 'chat' | 'shield' }[] = [
  { key: 'notice', label: 'Legal Notice', icon: 'file' },
  { key: 'bail', label: 'Bail Application', icon: 'gavel' },
  { key: 'reply', label: 'Reply to Notice', icon: 'chat' },
  { key: 'affidavit', label: 'Affidavit', icon: 'shield' },
];

export const REVIEW_FLAG = 'AI-generated draft · review before use';

export const DRAFTS_KEY = ['drafts'] as const;

export function useDrafts() {
  return useQuery({ queryKey: DRAFTS_KEY, queryFn: () => api.get<Draft[]>('/drafts') });
}

export function useDraftActions() {
  const client = useQueryClient();
  const refresh = () => {
    void client.invalidateQueries({ queryKey: DRAFTS_KEY });
    void client.invalidateQueries({ queryKey: ['dashboard'] });
  };
  return {
    create: async (template: TemplateKey, caseId: string | null) => {
      const draft = await api.post<Draft>('/drafts', { template, case_id: caseId });
      refresh();
      return draft;
    },
    save: async (id: string, body: string) => {
      const draft = await api.put<Draft>(`/drafts/${id}`, { body });
      refresh();
      return draft;
    },
  };
}

/** Asks the server for a file and hands it to the browser. Only called from an explicit click. */
export async function exportDraft(draft: Draft, format: 'docx' | 'pdf'): Promise<void> {
  const response = await fetch(`/api/v1/drafts/${draft.id}/export`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ format }),
  });
  if (!response.ok) throw new ApiError(response.status, 'Export failed');
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${draft.title.replace(/[^\w\- ]+/g, '').trim().replace(/ /g, '_') || 'draft'}.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function editedAgo(iso: string, now: Date = new Date()): string {
  const minutes = Math.max(0, Math.round((now.getTime() - new Date(iso).getTime()) / 60000));
  if (minutes < 1) return 'Edited just now';
  if (minutes < 60) return `Edited ${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `Edited ${hours} hour${hours === 1 ? '' : 's'} ago`;
  const days = Math.round(hours / 24);
  return days === 1 ? 'Edited yesterday' : `Edited ${days} days ago`;
}
