import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, api } from './api';
import { ME_KEY, type Settings } from './auth';

export function useUpdateSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<Settings>) => api.patch<Settings>('/me/settings', patch),
    onSuccess: () => client.invalidateQueries({ queryKey: ME_KEY }),
  });
}

export function useUpdatePhone() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (phone: string) => api.patch('/me', { phone }),
    onSuccess: () => client.invalidateQueries({ queryKey: ME_KEY }),
  });
}

/** Downloads everything held about the signed-in user as a JSON file (DPDP access and export). */
export async function downloadMyData(): Promise<void> {
  const data = await api.get<unknown>('/me/data-export');
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'mrcourt-my-data.json';
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function deactivateAccount(): Promise<void> {
  return api.post<void>('/me/deactivate', { acknowledge_case_retention: true });
}

export interface PendingVerification {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  bar_registration_number: string | null;
}

export function usePendingVerifications(enabled: boolean) {
  return useQuery({
    queryKey: ['verifications'],
    enabled,
    queryFn: () => api.get<PendingVerification[]>('/admin/verifications'),
  });
}

export function useDecideVerification() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: 'verified' | 'rejected' }) =>
      api.post(`/admin/verifications/${id}`, { decision }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['verifications'] }),
  });
}

export const errorText = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
