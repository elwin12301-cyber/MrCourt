import { type FormEvent, useState } from 'react';
import { ApiError } from '../services/api';
import {
  ACT_LABEL,
  type Confidence,
  DOC_TYPES,
  type DetailField,
  OUTCOMES,
  TYPE_LABEL,
  useDocumentDetails,
  useSaveDetails,
} from '../services/knowledge';

const CONFIDENCE: Record<Confidence, string> = {
  found: 'Found in the text',
  likely: 'Likely – please check',
  not_found: 'Not found',
  confirmed: 'Confirmed by a person',
};

const LABELS: [string, string][] = [
  ['doc_type', 'Type'],
  ['court', 'Court'],
  ['case_numbers', 'Case numbers'],
  ['cnr', 'CNR'],
  ['case_title', 'Case title'],
  ['parties', 'Parties'],
  ['judges', 'Judges'],
  ['decided_on', 'Date'],
  ['acts', 'Acts and sections'],
  ['outcome', 'Outcome'],
  ['language', 'Language'],
];
const EDITABLE = ['doc_type', 'court', 'case_numbers', 'case_title', 'judges', 'decided_on', 'outcome'];
const LIST_FIELDS = ['case_numbers', 'judges'];

function show(name: string, value: unknown): string {
  if (value === null || value === undefined || (Array.isArray(value) && value.length === 0)) return '—';
  if (name === 'doc_type') return TYPE_LABEL[String(value)] ?? String(value);
  if (name === 'language') return ({ en: 'English', ta: 'Tamil', mixed: 'English and Tamil' } as Record<string, string>)[String(value)] ?? String(value);
  if (name === 'acts')
    return (value as { act: string; section: string | null }[])
      .map((a) => `${ACT_LABEL[a.act] ?? a.act}${a.section ? ` s. ${a.section}` : ''}`)
      .join('; ');
  if (name === 'parties') {
    const p = value as { petitioner: string[]; respondent: string[] };
    return `${p.petitioner.join(', ')} v. ${p.respondent.join(', ')}`;
  }
  if (name === 'decided_on') return new Date(`${String(value)}T00:00:00`).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
  return Array.isArray(value) ? value.join(', ') : String(value);
}

function asText(name: string, field: DetailField | undefined): string {
  const v = field?.value;
  if (v === null || v === undefined) return '';
  return LIST_FIELDS.includes(name) && Array.isArray(v) ? v.join(', ') : String(v);
}

/** A document's mapped details with how sure MrCourt is about each, and a form to correct them. */
export function DocumentDetails({ id, title }: { id: string; title: string }) {
  const { data, isLoading, isError } = useDocumentDetails(id);
  const save = useSaveDetails(id);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  if (isLoading) return <p className="fine">Loading details…</p>;
  if (isError || !data) return <p className="fine" role="alert">Could not load the details.</p>;

  function start() {
    setDraft(Object.fromEntries(EDITABLE.map((n) => [n, asText(n, data!.fields[n])])));
    setEditing(true);
    setError(null);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const changed: Record<string, unknown> = {};
    for (const name of EDITABLE) {
      if (draft[name] === asText(name, data!.fields[name])) continue;
      const raw = draft[name].trim();
      changed[name] = !raw ? null : LIST_FIELDS.includes(name) ? raw.split(',').map((s) => s.trim()).filter(Boolean) : raw;
    }
    if (!Object.keys(changed).length) return setEditing(false);
    try {
      await save.mutateAsync(changed);
      setEditing(false);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not save. Please try again.');
    }
  }

  return (
    <section aria-label={`Details of ${title}`} className="docdetails">
      {data.text_quality === 'unreadable' && (
        <p role="note" className="fine" style={{ fontWeight: 600 }}>
          Text could not be read: this file needs OCR (scanning) before its details can be found.
        </p>
      )}
      {!editing ? (
        <>
          <dl>
            {LABELS.map(([name, label]) => {
              const field = data.fields[name];
              return (
                <div key={name}>
                  <dt>{label}</dt>
                  <dd>
                    {show(name, field?.value)}{' '}
                    <small>
                      ({CONFIDENCE[field?.confidence ?? 'not_found']}
                      {field?.alternatives?.length ? `; also seen: ${field.alternatives.map((a) => show(name, a)).join(', ')}` : ''})
                    </small>
                  </dd>
                </div>
              );
            })}
          </dl>
          {data.can_edit && (
            <button type="button" className="btn small outline" onClick={start}>
              Correct details
            </button>
          )}
        </>
      ) : (
        <form className="stack" onSubmit={submit} aria-label={`Correct the details of ${title}`}>
          {EDITABLE.map((name) => {
            const label = LABELS.find(([n]) => n === name)![1];
            const id = `det-${data.document_id}-${name}`;
            if (name === 'doc_type' || name === 'outcome') {
              const values = name === 'doc_type' ? DOC_TYPES : OUTCOMES;
              return (
                <label key={name} className="field" htmlFor={id}>
                  {label}
                  <select id={id} value={draft[name]} onChange={(e) => setDraft({ ...draft, [name]: e.target.value })}>
                    <option value="">None</option>
                    {values.map((v) => (
                      <option key={v} value={v}>
                        {name === 'doc_type' ? TYPE_LABEL[v] : v}
                      </option>
                    ))}
                  </select>
                </label>
              );
            }
            return (
              <label key={name} className="field" htmlFor={id}>
                {label}
                {LIST_FIELDS.includes(name) ? ' (separate with commas)' : name === 'decided_on' ? ' (YYYY-MM-DD)' : ''}
                <input
                  id={id}
                  type={name === 'decided_on' ? 'date' : 'text'}
                  value={draft[name]}
                  onChange={(e) => setDraft({ ...draft, [name]: e.target.value })}
                  maxLength={300}
                />
              </label>
            );
          })}
          {error && (
            <p role="alert" style={{ color: 'var(--danger, #b42318)', margin: 0 }}>
              {error}
            </p>
          )}
          <div style={{ display: 'flex', gap: 10 }}>
            <button type="submit" className="btn small" disabled={save.isPending}>
              {save.isPending ? 'Saving…' : 'Save corrections'}
            </button>
            <button type="button" className="btn small ghost" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
          <p className="fine" style={{ margin: 0 }}>Your corrections are kept when the details are mapped again.</p>
        </form>
      )}
    </section>
  );
}
