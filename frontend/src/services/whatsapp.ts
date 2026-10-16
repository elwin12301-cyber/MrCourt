import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, api } from './api';

export type ConsentKind = 'codes' | 'reminders' | 'updates' | 'activity';

export interface ConsentKindInfo {
  kind: ConsentKind;
  enabled: boolean;
  changed_at: string | null;
  describes: string;
}

export interface WhatsAppSettings {
  available: boolean;
  linked: boolean;
  number: string | null;
  can_link: boolean;
  kinds: ConsentKindInfo[];
  last_sent_at: string | null;
}

export const WHATSAPP_KEY = ['whatsapp'] as const;

export const KIND_LABEL: Record<ConsentKind, string> = {
  codes: 'Sign-in and verification codes',
  reminders: 'Hearing reminders',
  updates: 'Case updates',
  activity: 'Client activity',
};

export function useWhatsApp() {
  return useQuery({ queryKey: WHATSAPP_KEY, queryFn: () => api.get<WhatsAppSettings>('/me/whatsapp') });
}

function useWhatsAppMutation<T>(fn: (input: T) => Promise<WhatsAppSettings | void>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => client.invalidateQueries({ queryKey: WHATSAPP_KEY }),
  });
}

export function useLinkWhatsApp() {
  return useWhatsAppMutation<void>(() => api.post<WhatsAppSettings>('/me/whatsapp/link'));
}

export function useUnlinkWhatsApp() {
  return useWhatsAppMutation<void>(() => api.delete<void>('/me/whatsapp'));
}

export function useSetWhatsAppKind() {
  return useWhatsAppMutation<{ kind: ConsentKind; enabled: boolean }>(({ kind, enabled }) =>
    api.put<WhatsAppSettings>(`/me/whatsapp/consents/${kind}`, { enabled }),
  );
}

/** A short plain sentence for an error code the server returns. */
export function whatsappError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.message === 'phone_not_verified') return 'Verify your mobile number first.';
    if (error.message === 'number_in_use') return 'This number cannot be linked. Try another number.';
    if (error.message === 'not_linked') return 'Link WhatsApp first.';
  }
  return 'That did not work. Please try again.';
}
