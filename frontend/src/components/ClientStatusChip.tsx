import { CLIENT_STATUS_LABEL, type ClientStatus } from '../services/client';
import { Chip, type ChipTone } from './ui';

const TONE: Record<ClientStatus, ChipTone> = {
  notice_stage: 'soon',
  hearing_scheduled: 'active',
  awaiting_order: 'soon',
  closed: 'closed',
};

/** The client-facing status in words (colour is never the only signal). */
export function ClientStatusChip({ status }: { status: ClientStatus | null }) {
  if (!status) return <Chip tone="closed">Not shared yet</Chip>;
  return <Chip tone={TONE[status]}>{CLIENT_STATUS_LABEL[status]}</Chip>;
}
