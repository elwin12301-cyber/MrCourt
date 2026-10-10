import { dayOf } from '../services/cases';
import type { ClientCase } from '../services/client';

/** Who can see this case and the client's messages about it. */
export function AccessPanel({ access }: { access: ClientCase['access'] }) {
  const others = access.other_people_with_access;
  return (
    <div className="card" id="who-can-see">
      <h2 style={{ marginBottom: 10 }}>Who can see my case</h2>
      <p style={{ margin: '0 0 8px' }}>
        <b>{access.advocate_name}</b> can see this case, and the questions you send about it
        {access.since ? `, since ${dayOf(access.since)}` : ''}.
      </p>
      {others > 0 ? (
        <p className="fine" style={{ margin: 0 }}>
          {others === 1 ? '1 other person' : `${others} other people`} on this case can see the
          status, hearings and items your lawyer shares. They cannot see your questions or your
          lawyer's replies to you.
        </p>
      ) : (
        <p className="fine" style={{ margin: 0 }}>
          No one else has been given access to this case.
        </p>
      )}
    </div>
  );
}
