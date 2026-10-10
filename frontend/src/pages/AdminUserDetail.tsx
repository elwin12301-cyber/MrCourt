import { useQueryClient } from '@tanstack/react-query';
import { type FormEvent, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { PersonQuestions } from '../components/PersonQuestions';
import { Button, Chip } from '../components/ui';
import {
  ADMIN_KEY,
  type UserDetail,
  decideVerification,
  editPerson,
  reactivatePerson,
  signPersonOut,
  suspendPerson,
  useAdminAction,
  usePerson,
} from '../services/admin';
import { ApiError } from '../services/api';
import { dayOf } from '../services/cases';
import { StatusChip, VerificationChip } from './AdminUsers';

const field = { padding: '13px 16px' } as const;
const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);

export default function AdminUserDetail() {
  const { userId } = useParams();
  const client = useQueryClient();
  const { data: p, isLoading, error } = usePerson(userId);

  // The person's page is loaded once per visit (loading it is logged), so changes are applied to the
  // copy on screen from what the server returned instead of loading the page again.
  const apply = (patch: Partial<UserDetail>) =>
    client.setQueryData<UserDetail>([...ADMIN_KEY, 'person', userId], (old) => (old ? { ...old, ...patch } : old));
  const refreshLists = () => {
    for (const key of ['people', 'overview', 'audit']) void client.invalidateQueries({ queryKey: [...ADMIN_KEY, key] });
  };

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [bar, setBar] = useState('');
  const [note, setNote] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null);
  const [reason, setReason] = useState('');

  useEffect(() => {
    if (p) {
      setName(p.full_name);
      setEmail(p.email ?? '');
      setPhone(p.phone ?? '');
      setBar(p.bar_registration_number ?? '');
    }
  }, [p?.id, p?.full_name, p?.email, p?.phone, p?.bar_registration_number]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = useAdminAction((patch: Parameters<typeof editPerson>[1]) => editPerson(userId as string, patch));
  const suspend = useAdminAction((r: string) => suspendPerson(userId as string, r));
  const reactivate = useAdminAction(() => reactivatePerson(userId as string));
  const signOut = useAdminAction(() => signPersonOut(userId as string));
  const verify = useAdminAction((d: 'verified' | 'rejected') => decideVerification(userId as string, d));

  if (isLoading) return <section className="view" aria-busy="true" />;
  if (error || !p) {
    return (
      <section className="view">
        <Link to="/admin/advocates" className="back">
          <Icon name="back" />
          Back
        </Link>
        <h1>Person not found</h1>
        <p className="sub">They may not exist, or this account is not managed here.</p>
      </section>
    );
  }

  const isAdvocate = p.role === 'advocate';
  const listPath = isAdvocate ? '/admin/advocates' : '/admin/clients';
  const deactivated = p.status === 'deactivated';

  async function submit(event: FormEvent) {
    event.preventDefault();
    setNote(null);
    const patch: Parameters<typeof editPerson>[1] = {};
    if (name.trim() !== p!.full_name) patch.full_name = name.trim();
    if (email.trim() !== (p!.email ?? '')) patch.email = email.trim();
    if (phone.trim() !== (p!.phone ?? '')) patch.phone = phone.trim();
    if (isAdvocate && bar.trim() !== (p!.bar_registration_number ?? '')) patch.bar_registration_number = bar.trim();
    if (Object.keys(patch).length === 0) {
      setNote({ kind: 'error', text: 'Nothing has been changed.' });
      return;
    }
    try {
      const row = await save.mutateAsync(patch);
      apply(row as Partial<UserDetail>);
      refreshLists();
      setNote({ kind: 'ok', text: 'Saved.' });
    } catch (e) {
      setNote({ kind: 'error', text: msg(e, 'Could not save.') });
    }
  }

  async function run(action: () => Promise<unknown>, after: () => void, done: string) {
    setNote(null);
    try {
      await action();
      after();
      refreshLists();
      setNote({ kind: 'ok', text: done });
    } catch (e) {
      setNote({ kind: 'error', text: msg(e, 'That did not work. Please try again.') });
    }
  }

  return (
    <section className="view" id="admin-person" data-view="admin-person">
      <Link to={listPath} className="back">
        <Icon name="back" />
        {isAdvocate ? 'All advocates' : 'All clients'}
      </Link>
      <div>
        <h1>{p.full_name}</h1>
        <p style={{ margin: '10px 0 0', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Chip tone="closed">{isAdvocate ? 'Advocate' : 'Client'}</Chip>
          <StatusChip status={p.status} />
          {isAdvocate && <VerificationChip status={p.verification_status} />}
        </p>
      </div>
      <p className="advicenotice" role="note" style={{ margin: 0 }}>
        Opening this page is recorded in the audit log.
      </p>
      {note && (
        <p className="fine" role={note.kind === 'error' ? 'alert' : 'status'} style={{ fontWeight: 600, margin: 0 }}>
          {note.text}
        </p>
      )}

      <div className="row" style={{ alignItems: 'flex-start' }}>
        <form className="card" onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }} aria-label="Details">
          <h2>Details</h2>
          {deactivated && (
            <p className="fine" style={{ margin: 0 }}>
              This person deactivated their account, so their details were removed and cannot be edited.
            </p>
          )}
          <label className="field" htmlFor="ad-name">
            Full name
            <input id="ad-name" style={field} value={name} onChange={(e) => setName(e.target.value)} disabled={deactivated} required />
          </label>
          <label className="field" htmlFor="ad-email">
            Email
            <input id="ad-email" style={field} type="email" value={email} onChange={(e) => setEmail(e.target.value)} disabled={deactivated} />
          </label>
          <label className="field" htmlFor="ad-phone">
            Phone
            <input id="ad-phone" style={field} type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} disabled={deactivated} />
          </label>
          {isAdvocate && (
            <label className="field" htmlFor="ad-bar">
              Bar Council registration number
              <input id="ad-bar" style={field} value={bar} onChange={(e) => setBar(e.target.value)} disabled={deactivated} />
            </label>
          )}
          <div>
            <Button type="submit" small disabled={deactivated || save.isPending}>
              Save changes
            </Button>
          </div>
          {isAdvocate && <p className="fine" style={{ margin: 0 }}>Changing the Bar Council number asks for it to be confirmed again.</p>}
        </form>

        <div className="stack">
          {isAdvocate && p.verification_status === 'pending' && (
            <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <h2>Bar Council number</h2>
              <p style={{ margin: 0 }}>
                <b>{p.bar_registration_number}</b> is waiting to be confirmed.
              </p>
              <div style={{ display: 'flex', gap: 10 }}>
                <Button small disabled={verify.isPending} onClick={() => void run(() => verify.mutateAsync('verified'), () => apply({ verification_status: 'verified' }), 'Number confirmed.')}>
                  Confirm number
                </Button>
                <Button small variant="ghost" disabled={verify.isPending} onClick={() => void run(() => verify.mutateAsync('rejected'), () => apply({ verification_status: 'none', bar_registration_number: null }), 'Number rejected.')}>
                  Reject number
                </Button>
              </div>
            </div>
          )}

          {!deactivated && (
            <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <h2>Account</h2>
              {p.status === 'suspended' && p.suspension && (
                <p className="fine" style={{ margin: 0 }}>
                  Suspended {dayOf(p.suspension.at)} by {p.suspension.by}. Reason: {p.suspension.reason}
                </p>
              )}
              {p.status === 'suspended' ? (
                <div>
                  <Button
                    small
                    disabled={reactivate.isPending}
                    onClick={() => void run(() => reactivate.mutateAsync(undefined), () => apply({ status: 'active', suspension: null }), 'Account reactivated.')}
                  >
                    Reactivate account
                  </Button>
                </div>
              ) : (
                <>
                  <label className="field" htmlFor="suspend-reason">
                    Reason for suspending
                    <textarea
                      id="suspend-reason"
                      rows={2}
                      maxLength={500}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      style={{ font: 'inherit', padding: 10, borderRadius: 10, border: '1px solid var(--line)', background: 'var(--surface)', color: 'var(--ink)' }}
                    />
                  </label>
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    <Button
                      small
                      variant="ghost"
                      disabled={suspend.isPending || !reason.trim()}
                      onClick={() =>
                        void run(
                          () => suspend.mutateAsync(reason.trim()),
                          () => {
                            apply({ status: 'suspended', suspension: { reason: reason.trim(), at: new Date().toISOString(), by: 'you' } });
                            setReason('');
                          },
                          'Account suspended. They have been signed out.',
                        )
                      }
                    >
                      Suspend account
                    </Button>
                    <Button small variant="ghost" disabled={signOut.isPending} onClick={() => void run(() => signOut.mutateAsync(undefined), () => undefined, 'Signed out everywhere.')}>
                      Sign out everywhere
                    </Button>
                  </div>
                </>
              )}
              <p className="fine" style={{ margin: 0 }}>
                A suspended person is signed out at once and cannot sign in until reactivated.
              </p>
            </div>
          )}

          <div className="card">
            <h2 style={{ marginBottom: 10 }}>{isAdvocate ? 'Their cases' : 'Their cases and lawyers'}</h2>
            {p.cases.length === 0 && <p className="sub">No cases.</p>}
            {p.cases.map((c) => (
              <div className="act" key={c.id}>
                <Link to={`/admin/cases/${c.id}`}>
                  <b>{c.title}</b>
                </Link>
                <span>
                  {c.status === 'closed' ? 'Closed' : 'Open'}
                  {!isAdvocate ? ` · Lawyer: ${c.advocate_name}` : ''}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
      <PersonQuestions userId={p.id} />
    </section>
  );
}
