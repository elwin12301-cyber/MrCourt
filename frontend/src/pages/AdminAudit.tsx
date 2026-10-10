import { useState } from 'react';
import { AuditList } from '../components/AuditList';
import { Button } from '../components/ui';
import { useAuditLog } from '../services/admin';

function Page({ before }: { before: string | null }) {
  const { data, isLoading, isError } = useAuditLog(before);
  const [more, setMore] = useState(false);
  if (isLoading) return <p className="sub">Loading…</p>;
  if (isError || !data) {
    return (
      <p className="sub" role="alert">
        We could not load the audit log. Please try again.
      </p>
    );
  }
  return (
    <>
      <AuditList items={data.items} />
      {data.next_before && !more && (
        <div style={{ marginTop: 12 }}>
          <Button small variant="ghost" onClick={() => setMore(true)}>
            Load older entries
          </Button>
        </div>
      )}
      {data.next_before && more && <Page before={data.next_before} />}
    </>
  );
}

/** Who did what, newest first. Entries cannot be changed or removed by anyone. */
export default function AdminAudit() {
  return (
    <section className="view" id="admin-audit" data-view="admin-audit">
      <div>
        <h1>Audit log</h1>
        <p className="sub">
          Every account change, verification decision, full case view and document download by an administrator.
          Entries cannot be edited or deleted.
        </p>
      </div>
      <div className="card">
        <Page before={null} />
      </div>
    </section>
  );
}
