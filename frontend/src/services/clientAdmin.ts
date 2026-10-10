import { useQuery } from '@tanstack/react-query';
import { api } from './api';
import type { ClientStatus } from './client';

export interface TimelineAdvocate {
  id: string;
  kind: string;
  text: string;
  occurred_at: string;
  shared_with_client: boolean;
}

export interface ClientOnCase {
  id: string;
  contact_or_name: string;
  status: 'pending' | 'accepted' | 'removed';
  accepted_at: string | null;
}

export interface ClientContact {
  phone: string | null;
  email: string | null;
  office: string | null;
}

/** Entries of these kinds are always shown to clients, so the advocate cannot hide them. */
export const ALWAYS_VISIBLE = new Set(['status_change', 'hearing_scheduled', 'hearing_rescheduled', 'update']);

// Keys start with ['case', id] so the existing case mutations refresh them too.
export function useTimeline(caseId: string) {
  return useQuery({
    queryKey: ['case', caseId, 'timeline'],
    queryFn: () => api.get<TimelineAdvocate[]>(`/cases/${caseId}/timeline`),
  });
}

export function useClientsOnCase(caseId: string) {
  return useQuery({
    queryKey: ['case', caseId, 'clients'],
    queryFn: () => api.get<ClientOnCase[]>(`/cases/${caseId}/invitations`),
  });
}

export function useContactCard() {
  return useQuery({
    queryKey: ['contact-card'],
    queryFn: () => api.get<ClientContact>('/me/client-contact'),
  });
}

export const setClientStatus = (caseId: string, status: ClientStatus) =>
  api.put(`/cases/${caseId}/client-status`, { status });
export const postClientUpdate = (caseId: string, message: string) =>
  api.post(`/cases/${caseId}/client-updates`, { message });
export const addTimelineNote = (caseId: string, text: string, shared: boolean) =>
  api.post(`/cases/${caseId}/timeline`, { text, shared_with_client: shared });
export const setEntrySharing = (caseId: string, entryId: string, shared: boolean) =>
  api.put(`/cases/${caseId}/timeline/${entryId}/sharing`, { shared });
export const setDocumentSharing = (caseId: string, documentId: string, shared: boolean) =>
  api.put(`/cases/${caseId}/documents/${documentId}/sharing`, { shared });
export const setHearingOutcome = (caseId: string, hearingId: string, outcome: string, shared: boolean) =>
  api.put(`/cases/${caseId}/hearings/${hearingId}/outcome`, { outcome, shared });
export const removeClient = (caseId: string, invitationId: string) =>
  api.delete<void>(`/cases/${caseId}/invitations/${invitationId}`);
export const saveContactCard = (card: ClientContact) => api.put<ClientContact>('/me/client-contact', card);

export interface ClientQuestionAdvocate {
  id: string;
  kind: 'question' | 'update_request';
  text: string;
  sent_at: string;
  reply_text: string | null;
  replied_at: string | null;
  client_name: string;
}

export function useClientQuestions(caseId: string) {
  return useQuery({
    queryKey: ['case', caseId, 'client-questions'],
    queryFn: () => api.get<ClientQuestionAdvocate[]>(`/cases/${caseId}/client-questions`),
  });
}

export const replyToClient = (questionId: string, text: string) =>
  api.post<ClientQuestionAdvocate>(`/client-questions/${questionId}/reply`, { text });
