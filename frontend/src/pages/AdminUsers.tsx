import { type KeyboardEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { Chip, Pill } from '../components/ui';
import { type PersonStatus, type StatusFilter, type UserRow, usePeople } from '../services/admin';

export const STATUS_LABEL: Record<PersonStatus, string> = {
  active: 'Active',
  suspended: 'Suspended',
  deactivated: 'Deactivated',
};

export function StatusChip({ status }: { status: PersonStatus }) {
  return <Chip tone={status === 'active' ? 'ok' : status === 'suspended' ? 'soon' : 'closed'}>{STATUS_LABEL[status]}</Chip>;
}

export function VerificationChip({ status }: { status: UserRow['verification_status'] }) {
  if (status === 'verified') return <Chip tone="ok">Bar Council verified</Chip>;
  if (status === 'pending') return <Chip tone="soon">Waiting for verification</Chip>;
  return <Chip tone="closed">Not verified</Chip>;
}

/** Every advocate, or every client. Opening a person goes to their page. */
export default function AdminUsers({ kind }: { kind: 'advocate' | 'petitioner' }) {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<StatusFilter>('all');
  const isAdvocate = kind === 'advocate';
  const noun = isAdvocate ? 'Advocates' : 'Clients';
  const { data, isLoading, isError } = usePeople(kind, search, filter);

  const filters: { value: StatusFilter; label: string }[] = [
    { value: 'all', label: 'All' },
    { value: 'active', label: 'Active' },
    { value: 'suspended', label: 'Suspended' },
    { value: 'deactivated', label: 'Deactivated' },
    ...(isAdvocate ? [{ value: 'pending' as const, label: 'Waiting for verification' }] : []),
  ];

  const open = (id: string) => navigate(`/admin/${isAdvocate ? 'advocates' : 'clients'}/${id}`);
  const onKey = (e: KeyboardEvent, id: string) => {
    if (e.key === 'Enter') open(id);
  };

  return (
    <section className="view" id="admin-people" data-view={`admin-${kind}`}>
      <div>
        <h1>{noun}</h1>
        <p className="sub">{data ? `${data.length} ${data.length === 1 ? 'person' : 'people'} shown` : ''}</p>
      </div>
      <div className="bar" style={{ maxWidth: 'none' }}>
        <Icon name="search" style={{ color: 'var(--muted)' }} />
        <input
          aria-label={`Search ${noun.toLowerCase()}`}
          placeholder="Search by name, email or phone"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      <div className="suggest" role="group" aria-label="Filter by status">
        {filters.map((f) => (
          <Pill key={f.value} pressed={filter === f.value} onClick={() => setFilter(f.value)}>
            {f.label}
          </Pill>
        ))}
      </div>
      <div className="card tablewrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Contact</th>
              <th>Status</th>
              {isAdvocate && <th>Bar Council</th>}
              <th>Cases</th>
            </tr>
          </thead>
          <tbody>
            {isError && (
              <tr>
                <td colSpan={5} style={{ color: 'var(--muted)' }}>
                  Could not load the list. Please try again.
                </td>
              </tr>
            )}
            {!isError && !isLoading && data?.length === 0 && (
              <tr>
                <td colSpan={5} style={{ color: 'var(--muted)' }}>
                  No one matches.
                </td>
              </tr>
            )}
            {data?.map((u) => (
              // Rows open the person on click or Enter, like the case list.
              // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex, jsx-a11y/no-noninteractive-element-interactions
              <tr key={u.id} tabIndex={0} onClick={() => open(u.id)} onKeyDown={(e) => onKey(e, u.id)}>
                <td>
                  <b>{u.full_name}</b>
                </td>
                <td>
                  {u.email ?? '—'}
                  <small>{u.phone ?? ''}</small>
                </td>
                <td>
                  <StatusChip status={u.status} />
                </td>
                {isAdvocate && (
                  <td>
                    {u.bar_registration_number ?? '—'}
                    <small>{u.verification_status === 'verified' ? 'Verified' : u.verification_status === 'pending' ? 'Waiting' : ''}</small>
                  </td>
                )}
                <td>{u.case_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
