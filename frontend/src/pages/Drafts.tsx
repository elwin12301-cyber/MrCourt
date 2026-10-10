import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { ExportDialog } from '../components/ExportDialog';
import { Icon } from '../components/Icon';
import { Button, Chip } from '../components/ui';
import { useMe } from '../services/auth';
import { useCases } from '../services/cases';
import {
  type Draft,
  REVIEW_FLAG,
  TEMPLATES,
  type TemplateKey,
  editedAgo,
  useDraftActions,
  useDrafts,
} from '../services/drafts';

function DraftsScreen() {
  const location = useLocation();
  const [caseId, setCaseId] = useState<string>((location.state as { caseId?: string } | null)?.caseId ?? '');
  const [template, setTemplate] = useState<TemplateKey>('notice');
  const [editing, setEditing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const letter = useRef<HTMLDivElement>(null);

  const { data: cases } = useCases('', 'all');
  const { data: drafts, isLoading } = useDrafts();
  const actions = useDraftActions();
  const creating = useRef<string | null>(null);

  const current: Draft | undefined = drafts?.find(
    (d) => d.template === template && (d.case_id ?? '') === caseId,
  );

  // Selecting a template shows its draft for the chosen case, generating one the first time.
  useEffect(() => {
    if (isLoading || current) return;
    const key = `${template}:${caseId}`;
    if (creating.current === key) return;
    creating.current = key;
    actions
      .create(template, caseId || null)
      .catch(() => setError('Could not create the draft. Please try again.'))
      .finally(() => {
        creating.current = null;
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run only when the selection changes
  }, [template, caseId, isLoading, current?.id]);

  function select(key: TemplateKey) {
    setTemplate(key);
    setEditing(false);
    setExporting(false);
    setError(null);
  }

  async function toggleEdit() {
    if (!current) return;
    if (!editing) {
      setEditing(true);
      setTimeout(() => letter.current?.focus(), 0);
      return;
    }
    const text = (letter.current?.innerText ?? current.body).replace(/\r\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
    setEditing(false);
    if (text === current.body) return;
    try {
      await actions.save(current.id, text);
      setError(null);
    } catch {
      setError('Could not save your edits. Please try again.');
    }
  }

  return (
    <section className="view" id="drafts" data-view="drafts">
      <div>
        <h1>Drafts</h1>
        <p className="sub">AI-assisted, always editable by you</p>
      </div>

      <label className="field" htmlFor="draft-case" style={{ maxWidth: 420 }}>
        For case
        <select
          id="draft-case"
          value={caseId}
          onChange={(e) => {
            setCaseId(e.target.value);
            setEditing(false);
          }}
        >
          <option value="">No case (blank placeholders)</option>
          {cases?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.title}
            </option>
          ))}
        </select>
      </label>

      <div className="tpl" id="tpl" role="group" aria-label="Templates">
        {TEMPLATES.map((t) => (
          <button
            key={t.key}
            type="button"
            className="card"
            aria-pressed={template === t.key}
            onClick={() => select(t.key)}
          >
            <span className="ico">
              <Icon name={t.icon} />
            </span>
            {t.label}
          </button>
        ))}
      </div>

      <div className="card" style={{ maxWidth: 860 }}>
        {!current ? (
          <p className="sub" role="status">
            {error ?? 'Preparing your draft…'}
          </p>
        ) : (
          <>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                gap: 12,
                alignItems: 'flex-start',
                flexWrap: 'wrap',
              }}
            >
              <div>
                <h2 id="dTitle">{current.title}</h2>
                <span style={{ color: 'var(--muted)', fontSize: 12 }} id="dMeta">
                  {current.subtitle} · {editedAgo(current.last_edited_at)}
                </span>
              </div>
              <Chip tone="soon">Draft v{current.version}</Chip>
            </div>
            <hr style={{ border: 0, borderTop: '1px solid var(--line)', margin: '16px 0' }} />
            <div
              key={`${current.id}-${current.version}`}
              ref={letter}
              className="letter"
              id="letter"
              role="textbox"
              aria-multiline="true"
              aria-label="Draft text"
              tabIndex={editing ? 0 : -1}
              contentEditable={editing}
              suppressContentEditableWarning
            >
              {current.body}
            </div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 18, flexWrap: 'wrap' }}>
              <span className="disc" style={{ margin: 0, flex: 1, minWidth: 200 }}>
                <Icon name="shield" />
                {REVIEW_FLAG}
              </span>
              <Button small id="editBtn" onClick={() => void toggleEdit()}>
                {editing ? 'Done' : 'Edit'}
              </Button>
              <Button small variant="ghost" id="exportBtn" onClick={() => setExporting((v) => !v)} aria-expanded={exporting}>
                Export
              </Button>
            </div>
            {exporting && <ExportDialog draft={current} onClose={() => setExporting(false)} />}
            {error && (
              <p className="fine" role="alert" style={{ marginTop: 10 }}>
                {error}
              </p>
            )}
          </>
        )}
      </div>
    </section>
  );
}

/** Drafts are for advocates only (FR-019); anyone else sees why, instead of a failing screen. */
export default function Drafts() {
  const { data: me } = useMe();
  if (!me) return null;
  if (me.role !== 'advocate') {
    return (
      <section className="view" id="drafts" data-view="drafts">
        <h1>Drafts</h1>
        <p className="sub">Drafts are available to advocates only.</p>
      </section>
    );
  }
  return <DraftsScreen />;
}
