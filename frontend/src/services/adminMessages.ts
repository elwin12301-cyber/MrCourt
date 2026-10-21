import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './api';

export interface MessageTotal {
  kind: string;
  channel: 'whatsapp' | 'sms';
  queued: number;
  sent: number;
  delivered: number;
  read: number;
  failed: number;
}

export interface ServiceHealth {
  provider: string;
  configured: boolean;
  healthy: boolean | null;
  last_ok_at: string | null;
}

export interface MessageSummary {
  days: number;
  service: ServiceHealth;
  totals: MessageTotal[];
}

export interface FailureRow {
  id: string;
  time: string;
  kind: string;
  person: string;
  reason: string;
  fell_back_to_sms: boolean;
  can_resend: boolean;
}

export interface FailuresPage {
  items: FailureRow[];
  next_before: string | null;
}

export const KIND_NAME: Record<string, string> = {
  code: 'Codes',
  reminder: 'Hearing reminders',
  update: 'Case updates',
  activity: 'Client activity',
};

export const REASON_TEXT: Record<string, string> = {
  not_on_whatsapp: 'Not on WhatsApp',
  template_missing: 'Message template not approved',
  window_closed: 'Reply window closed',
  provider_down: 'WhatsApp service unavailable',
  provider_error: 'WhatsApp refused it',
  not_delivered: 'WhatsApp held it back (marketing message to a new contact)',
  cap_reached: 'Daily limit reached',
  not_linked: 'Number no longer linked',
  not_configured: 'Not set up',
  rate_limited: 'Sending too fast',
  bad_number: 'Not a valid number',
};

export function useMessageSummary(days: number) {
  return useQuery({
    queryKey: ['admin', 'messages', 'summary', days],
    queryFn: () => api.get<MessageSummary>(`/admin/messages/summary?days=${days}`),
    refetchInterval: 30_000,
  });
}

/** Opening the failure list is recorded in the audit log (a count only), so it runs only when asked for. */
export function useMessageFailures(days: number, before: string | null, enabled: boolean) {
  const qs = `days=${days}${before ? `&before=${encodeURIComponent(before)}` : ''}`;
  return useQuery({
    queryKey: ['admin', 'messages', 'failures', days, before],
    enabled,
    gcTime: 3000,
    queryFn: () => api.get<FailuresPage>(`/admin/messages/failures?${qs}`),
  });
}

export function useResend() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<{ status: string }>(`/admin/messages/${id}/resend`),
    onSuccess: () => client.invalidateQueries({ queryKey: ['admin', 'messages'] }),
  });
}
