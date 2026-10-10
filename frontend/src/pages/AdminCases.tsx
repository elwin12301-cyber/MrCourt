import { type KeyboardEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { Chip } from '../components/ui';
import { useAdminCases } from '../services/admin';
import { dayOf } from '../services/cases';

/** Every case in the system. Listing shows overview fields only; opening one is recorded. */
export default function AdminCases() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const { data, isLoading, isError } = useAdminCases(search);
  const open = (id: string) => navigate(`/admin/cases/${id}`);
  const onKey = (e: KeyboardEvent, id: string) => {
    if (e.key === 'Enter') open(id);
  };

  return (
    <section className="view" id="admin-cases" data-view="admin-cases">
      <div>
        <h1>Cases</h1>
        <p className="sub">{data ? `${data.length} ${data.length === 1 ? 'case' : 'cases'} shown` : ''}</p>
      </div>
      <div className="bar" style={{ maxWidth: 'none' }}>
        <Icon name="search" style={{ color: 'var(--muted)' }} />
        <input
          aria-label="Search cases"
          placeholder="Search by case, court, party or advocate"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      <div className="card tablewrap">
        <table>
          <thead>
            <tr>
              <th>Case</th>
              <th>Advocate</th>
              <th>Clients</th>
              <th>Status</th>
              <th>Next hearing</th>
            </tr>
          </thead>
          <tbody>
            {isError && (
              <tr>
                <td colSpan={5} style={{ color: 'var(--muted)' }}>
                  Could not load the cases. Please try again.
                </td>
              </tr>
            )}
            {!isError && !isLoading && data?.length === 0 && (
              <tr>
                <td colSpan={5} style={{ color: 'var(--muted)' }}>
                  No cases match.
                </td>
              </tr>
            )}
            {data?.map((c) => (
              // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex, jsx-a11y/no-noninteractive-element-interactions
              <tr key={c.id} tabIndex={0} onClick={() => open(c.id)} onKeyDown={(e) => onKey(e, c.id)}>
                <td>
                  <b>{c.title}</b>
                  <small>{c.court}</small>
                </td>
                <td>{c.advocate_name}</td>
                <td>{c.client_count}</td>
                <td>
                  <Chip tone={c.status === 'closed' ? 'closed' : 'ok'}>{c.status === 'closed' ? 'Closed' : 'Open'}</Chip>
                </td>
                <td>{c.next_hearing_at ? dayOf(c.next_hearing_at) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
