import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from './api';

export interface Settings {
  language: string;
  whatsapp_reminders: boolean;
  hearing_alert_days: number;
  theme: 'system' | 'light' | 'dark';
}

export interface Me {
  id: string;
  role: 'advocate' | 'petitioner' | 'admin';
  full_name: string;
  bar_registration_number: string | null;
  phone: string | null;
  phone_verified: boolean;
  verification_status: 'none' | 'pending' | 'verified';
  is_admin: boolean;
  settings: Settings;
}

export const ME_KEY = ['me'] as const;

/** Current user, or null when signed out. A 401 is a normal state, not an error. */
export function useMe() {
  return useQuery({
    queryKey: ME_KEY,
    retry: false,
    staleTime: 60_000,
    queryFn: async (): Promise<Me | null> => {
      try {
        return await api.get<Me>('/me');
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
  });
}

export function useSignOut() {
  const client = useQueryClient();
  return async () => {
    try {
      await api.post('/auth/logout');
    } finally {
      client.clear();
      client.setQueryData(ME_KEY, null);
    }
  };
}
