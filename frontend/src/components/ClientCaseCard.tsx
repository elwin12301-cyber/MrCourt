import { Link } from 'react-router-dom';
import { dateTimeOf, dayOf } from '../services/cases';
import type { ClientCaseSummary } from '../services/client';
import { ClientStatusChip } from './ClientStatusChip';
import { Icon } from './Icon';

/** One case in the client's list: status, when it changed, the next hearing and the lawyer. */
export function ClientCaseCard({ item }: { item: ClientCaseSummary }) {
  const hearing = item.next_hearing;
  return (
    <Link to={`/cases/${item.id}`} className="card clientcase">
      <span className="clientcase-head">
        <b>{item.title}</b>
        <ClientStatusChip status={item.status} />
      </span>
      <span className="clientcase-line">
        {item.status && item.status_changed_at
          ? `Status updated ${dayOf(item.status_changed_at)}`
          : 'Your lawyer has not shared a status yet'}
      </span>
      <span className="clientcase-line">
        <Icon name="cal" size={16} />
        {hearing
          ? `Next hearing: ${dateTimeOf(hearing.scheduled_at)} · ${hearing.court}`
          : 'No hearing scheduled yet'}
      </span>
      <span className="clientcase-line">
        <Icon name="user" size={16} />
        My lawyer: {item.lawyer.name}
      </span>
    </Link>
  );
}
