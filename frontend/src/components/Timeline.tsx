import { dayOf } from '../services/cases';
import type { TimelineEntry } from '../services/client';

/** What has happened on a case, newest first. */
export function Timeline({ entries }: { entries: TimelineEntry[] }) {
  if (entries.length === 0) {
    return <p className="sub">Nothing has been shared yet.</p>;
  }
  return (
    <ol className="tl">
      {entries.map((entry) => (
        <li key={entry.id}>
          <time dateTime={entry.occurred_at}>{dayOf(entry.occurred_at)}</time>
          <span>{entry.text}</span>
        </li>
      ))}
    </ol>
  );
}
