import { type FormEvent, useState } from 'react';
import { DocumentDetails } from '../../components/DocumentDetails';
import { Icon } from '../../components/Icon';
import { SourceFilters } from '../../components/SourceFilters';
import { Button, Card, Chip } from '../../components/ui';
import { ApiError } from '../../services/api';
import { useMe } from '../../services/auth';
import {
  type DocumentKind,
  type DocumentStatus,
  type KnowledgeDocument,
  KIND_LABEL,
  STATUS_LABEL,
  type SourceFilterValues,
  useAddDocument,
  useDocuments,
  useRemap,
  useRemoveDocument,
} from '../../services/knowledge';

const TONE: Record<DocumentStatus, 'ok' | 'soon' | 'closed'> = { ready: 'ok', processing: 'soon', failed: 'closed' };

const textarea = {
  font: 'inherit',
  padding: 12,
  borderRadius: 10,
  border: '1px solid var(--line)',
  background: 'var(--surface)',
  color: 'var(--ink)',
} as const;

function AddForm({ admin, onDone }: { admin: boolean; onDone: () => void }) {
  const add = useAddDocument();
  const [title, setTitle] = useState('');
  const [citation, setCitation] = useState('');
  const [kind, setKind] = useState<DocumentKind>('judgment');
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await add.mutateAsync({ title, citation, kind: admin ? kind : undefined, text, file });
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not add this. Please try again.');
    }
  }

  return (
    <Card>
      <form className="stack" onSubmit={submit} aria-label="Add a source">
        <h2 style={{ margin: 0, fontSize: 20 }}>{admin ? 'Add a shared source' : 'Add a private note'}</h2>
        <p className="fine" style={{ margin: 0 }}>
          {admin
            ? 'Shared sources are used for everyone’s answers. Add text, a PDF or text file, or a scanned page or image in English or Tamil (10 MB at most).'
            : 'Only you can use and see this note. Add text, a PDF or text file, or a scanned page or image in English or Tamil (10 MB at most).'}
        </p>
        <label className="field">
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={300} required />
        </label>
        <label className="field">
          Citation (shown in answers)
          <input value={citation} onChange={(e) => setCitation(e.target.value)} maxLength={400} required />
        </label>
        {admin && (
          <label className="field">
            Kind
            <select value={kind} onChange={(e) => setKind(e.target.value as DocumentKind)}>
              <option value="judgment">Judgment</option>
              <option value="act_section">Act or section</option>
              <option value="note">Note</option>
            </select>
          </label>
        )}
        <label className="field">
          Text
          <textarea
            rows={5}
            style={textarea}
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={file !== null}
            placeholder="Paste the text here, or choose a file below"
          />
        </label>
        <label className="field">
          File (PDF, text or scanned image)
          <input type="file" accept=".pdf,.txt,.md,.png,.jpg,.jpeg,.tif,.tiff" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        {error && (
          <p role="alert" style={{ color: 'var(--danger, #b42318)', margin: 0 }}>
            {error}
          </p>
        )}
        <div style={{ display: 'flex', gap: 10 }}>
          <Button type="submit" disabled={add.isPending || !title.trim() || !citation.trim() || (!file && !text.trim())}>
            {add.isPending ? 'Adding…' : 'Add source'}
          </Button>
          <Button variant="ghost" onClick={onDone}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}

function Row({ doc }: { doc: KnowledgeDocument }) {
  const remove = useRemoveDocument();
  const [confirming, setConfirming] = useState(false);
  const [open, setOpen] = useState(false);
  return (
    <>
    <tr>
      <td>
        <b>{doc.title}</b>
        <small>{doc.citation}</small>
        {doc.details?.short && <small>{doc.details.short}</small>}
        {doc.details?.text_quality === 'unreadable' && <small>Text could not be read: needs OCR</small>}
      </td>
      <td>{KIND_LABEL[doc.kind]}</td>
      <td>{doc.scope === 'shared' ? 'Shared' : doc.owner ? `Private · ${doc.owner}` : 'Private to you'}</td>
      <td>
        <Chip tone={TONE[doc.status]}>{STATUS_LABEL[doc.status]}</Chip>
        {doc.ocr_pages ? <small>{doc.ocr_pages === 1 ? '1 page' : `${doc.ocr_pages} pages`} read by OCR</small> : null}
        {doc.status_reason && <small>{doc.status_reason}</small>}
      </td>
      <td>
        {doc.status === 'ready' && (
          <Button small variant="ghost" aria-expanded={open} aria-label={`${open ? 'Hide' : 'Show'} details of ${doc.title}`} onClick={() => setOpen((v) => !v)}>
            {open ? 'Hide details' : 'Details'}
          </Button>
        )}
        {doc.can_remove &&
          (confirming ? (
            <span role="group" aria-label={`Remove ${doc.title}?`} style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Button small onClick={() => remove.mutate(doc.id)} disabled={remove.isPending}>
                Yes, remove
              </Button>
              <Button small variant="ghost" onClick={() => setConfirming(false)}>
                Keep it
              </Button>
            </span>
          ) : (
            <Button small variant="ghost" aria-label={`Remove ${doc.title}`} onClick={() => setConfirming(true)}>
              Remove
            </Button>
          ))}
      </td>
    </tr>
    {open && (
      <tr className="detailsrow">
        <td colSpan={5}>
          <DocumentDetails id={doc.id} title={doc.title} />
        </td>
      </tr>
    )}
    </>
  );
}

function RemapButton({ admin }: { admin: boolean }) {
  const remap = useRemap();
  const summary = remap.data;
  return (
    <span style={{ display: 'inline-flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
      <Button variant="ghost" onClick={() => remap.mutate()} disabled={remap.isPending}>
        {remap.isPending ? 'Mapping…' : admin ? 'Map shared details again' : 'Map my documents again'}
      </Button>
      {summary && (
        <span role="status" className="fine">
          {summary.documents} documents mapped
          {summary.unreadable ? `, ${summary.unreadable} could not be read (need OCR)` : ''}. Your corrections were kept.
        </span>
      )}
    </span>
  );
}

/** The sources that feed answers. Administrators manage shared ones, advocates their own notes. */
export default function KnowledgeTab() {
  const me = useMe().data;
  const [search, setSearch] = useState('');
  const [adding, setAdding] = useState(false);
  const [filters, setFilters] = useState<SourceFilterValues>({});
  const { data, isLoading, isError } = useDocuments(search, filters);
  const canAdd = me?.role === 'admin' || me?.role === 'advocate';

  return (
    <div className="stack" id="knowledge">
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <div className="bar" style={{ maxWidth: 420, flex: 1 }}>
          <Icon name="search" style={{ color: 'var(--muted)' }} />
          <input
            aria-label="Search sources"
            placeholder="Search by title or citation"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {canAdd && !adding && <Button onClick={() => setAdding(true)}>{me?.role === 'admin' ? 'Add a source' : 'Add a private note'}</Button>}
        {canAdd && <RemapButton admin={me?.role === 'admin'} />}
      </div>
      <SourceFilters value={filters} onChange={setFilters} idPrefix="kb-filter" />
      {adding && <AddForm admin={me?.role === 'admin'} onDone={() => setAdding(false)} />}
      {/* The table scrolls sideways on narrow screens, so the region must be reachable by keyboard. */}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
      <div className="card tablewrap" tabIndex={0} role="region" aria-label="Knowledge sources">
        <table>
          <thead>
            <tr>
              <th>Source</th>
              <th>Kind</th>
              <th>Used for</th>
              <th>Status</th>
              <th>
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {isError && (
              <tr>
                <td colSpan={5} style={{ color: 'var(--muted)' }}>
                  Could not load the sources. Please try again.
                </td>
              </tr>
            )}
            {!isError && !isLoading && data?.length === 0 && (
              <tr>
                <td colSpan={5} style={{ color: 'var(--muted)' }}>
                  No sources match.
                </td>
              </tr>
            )}
            {data?.map((doc) => <Row key={doc.id} doc={doc} />)}
          </tbody>
        </table>
      </div>
      {me?.role === 'petitioner' && (
        <p className="fine">These are the sources MrCourt can use to answer your questions. Only your lawyer or an administrator can change them.</p>
      )}
    </div>
  );
}
