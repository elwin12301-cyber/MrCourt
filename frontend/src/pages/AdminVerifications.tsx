import { Button } from '../components/ui';
import { useMe } from '../services/auth';
import { useDecideVerification, usePendingVerifications } from '../services/account';

/** Administrators confirm each advocate's Bar Council registration number (FR-021). */
export default function AdminVerifications() {
  const { data: me } = useMe();
  const isAdmin = !!me?.is_admin;
  const { data, isLoading } = usePendingVerifications(isAdmin);
  const decide = useDecideVerification();
  if (!me) return null;
  if (!isAdmin) {
    return (
      <section className="view">
        <h1>Verifications</h1>
        <p className="sub">This page is for administrators only.</p>
      </section>
    );
  }
  return (
    <section className="view" id="verifications">
      <div>
        <h1>Verifications</h1>
        <p className="sub">Advocates waiting for Bar Council registration to be confirmed</p>
      </div>
      <div className="card">
        {!isLoading && data?.length === 0 && <p className="sub">Nobody is waiting.</p>}
        {data?.map((u) => (
          <div className="act" key={u.id} style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ flex: 1, minWidth: 220 }}>
              <b>{u.full_name}</b>
              <span>
                {u.bar_registration_number ?? 'No number'} · {u.email ?? u.phone ?? 'no contact'}
              </span>
            </span>
            <Button small data-voice-risk="verify" aria-label={`Confirm ${u.full_name}`} disabled={decide.isPending} onClick={() => decide.mutate({ id: u.id, decision: 'verified' })}>
              Confirm
            </Button>
            <Button small variant="ghost" data-voice-risk="verify" aria-label={`Reject ${u.full_name}`} disabled={decide.isPending} onClick={() => decide.mutate({ id: u.id, decision: 'rejected' })}>
              Reject
            </Button>
          </div>
        ))}
      </div>
    </section>
  );
}
