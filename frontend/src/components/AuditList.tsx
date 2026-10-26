import { Link } from 'react-router-dom';
import { dateTimeOf } from '../services/cases';
import { type AuditItem, describeDetail } from '../services/admin';

function targetLink(item: AuditItem): string | null {
  if (!item.target_id) return null;
  if (item.target_type === 'case') return `/admin/cases/${item.target_id}`;
  if (item.target_type === 'user') return `/admin/advocates/${item.target_id}`;
  return null;
}

/** Who did what, to whom or what, and when. Read-only. */
export function AuditList({ items }: { items: AuditItem[] }) {
  if (items.length === 0) return <p className="sub">Nothing has been recorded yet.</p>;
  return (
    <ul style={{ listStyle: 'none', margin: 0, padding: 0 }} aria-label="Audit entries">
      {items.map((item) => {
        const link = targetLink(item);
        const detail = describeDetail(item);
        return (
          <li className="act" key={item.id}>
            <b>
              {item.admin_name} · {item.action_label}
            </b>
            <span>
              {item.target_name ? (
                link ? (
                  <Link to={link}>{item.target_name}</Link>
                ) : (
                  item.target_name
                )
              ) : (
                item.target_type
              )}
              {detail ? ` · ${detail}` : ''} · <time dateTime={item.created_at}>{dateTimeOf(item.created_at)}</time>
            </span>
          </li>
        );
      })}
    </ul>
  );
}
