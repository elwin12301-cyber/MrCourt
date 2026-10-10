import { type KeyboardEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CaseForm } from '../components/CaseForm';
import { Icon } from '../components/Icon';
import { Button, Chip, Pill } from '../components/ui';
import { useMe } from '../services/auth';
import {
  type CaseStatus,
  STATUS_LABEL,
  STATUS_TONE,
  dayOf,
  useCases,
} from '../services/cases';

const FILTERS: { value: CaseStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'hearing_soon', label: 'Hearing soon' },
  { value: 'closed', label: 'Closed' },
];

export default function Cases() {
  const navigate = useNavigate();
  const { data: me } = useMe();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<CaseStatus | 'all'>('all');
  const [adding, setAdding] = useState(false);
  const { data: cases, isLoading, isError } = useCases(search, filter);
  const { data: everything } = useCases('', 'all');

  const open = (id: string) => navigate(`/cases/${id}`);
  const onKey = (event: KeyboardEvent, id: string) => {
    if (event.key === 'Enter') open(id);
  };

  const active = (everything ?? []).filter((c) => c.status !== 'closed');
  const courts = new Set(active.map((c) => c.court)).size;
  const summary = everything
    ? `${active.length} active matter${active.length === 1 ? '' : 's'} across ${courts} court${courts === 1 ? '' : 's'}`
    : '';

  return (
    <section className="view" id="cases" data-view="cases">
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div>
          <h1>Cases</h1>
          <p className="sub" id="caseCount">
            {summary}
          </p>
        </div>
        {me?.role === 'advocate' && !adding && (
          <Button variant="gold" onClick={() => setAdding(true)}>
            New case
          </Button>
        )}
      </div>
      {adding && <CaseForm onCancel={() => setAdding(false)} onCreated={(c) => open(c.id)} />}
      <div className="bar" style={{ maxWidth: 'none' }}>
        <Icon name="search" style={{ color: 'var(--muted)' }} />
        <input
          id="caseSearch"
          aria-label="Search cases"
          placeholder="Search by party, CNR number or court"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      <div className="suggest" id="filters" role="group" aria-label="Filter by status">
        {FILTERS.map((f) => (
          <Pill key={f.value} pressed={filter === f.value} onClick={() => setFilter(f.value)}>
            {f.label}
          </Pill>
        ))}
      </div>
      <div className="card tablewrap">
        <table>
          <thead>
            <tr>
              <th>Case</th>
              <th>Court</th>
              <th>Status</th>
              <th>Next hearing</th>
            </tr>
          </thead>
          <tbody id="caseRows">
            {isError && (
              <tr>
                <td colSpan={4} style={{ color: 'var(--muted)' }}>
                  Could not load cases. Please try again.
                </td>
              </tr>
            )}
            {!isError && !isLoading && cases?.length === 0 && (
              <tr>
                <td colSpan={4} style={{ color: 'var(--muted)' }}>
                  {search || filter !== 'all' ? 'No cases match your search.' : 'No cases yet.'}
                </td>
              </tr>
            )}
            {cases?.map((c) => (
              // Rows are focusable and open the case on click or Enter, as in the prototype.
              // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex, jsx-a11y/no-noninteractive-element-interactions
              <tr key={c.id} tabIndex={0} onClick={() => open(c.id)} onKeyDown={(e) => onKey(e, c.id)}>
                <td>
                  <b>{c.title}</b>
                  <small>CNR {c.cnr_number}</small>
                </td>
                <td>{c.court}</td>
                <td>
                  <Chip tone={STATUS_TONE[c.status]}>{STATUS_LABEL[c.status]}</Chip>
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
