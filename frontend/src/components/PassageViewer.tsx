import { useState } from 'react';
import { usePassage } from '../services/passages';

/** A cited source with a way to read the passage it points to, and where it came from. */
export function CitedSource({
  number,
  label,
  passageId,
  details,
}: {
  number: number;
  label: string;
  passageId?: string | null;
  details?: string | null;
}) {
  const [open, setOpen] = useState(false);
  const { data, isError, isLoading } = usePassage(passageId, open);
  const panel = `passage-${number}-${passageId ?? 'removed'}`;
  return (
    <div className="src" style={{ flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
        <b>[{number}]</b>
        <span>
          {label}
          {details && <small className="srcdetails">{details}</small>}
        </span>
        <button
          type="button"
          className="btn small ghost"
          aria-expanded={open}
          aria-controls={panel}
          aria-label={`${open ? 'Hide' : 'Read'} source ${number}`}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? 'Hide source' : 'Read source'}
        </button>
      </div>
      {open && (
        <div id={panel} role="region" aria-label={`Source ${number}`} style={{ fontWeight: 400 }}>
          {!passageId && <p style={{ margin: 0 }}>This source has since been removed, so its text is no longer available.</p>}
          {passageId && isLoading && <p style={{ margin: 0 }}>Opening…</p>}
          {passageId && isError && <p style={{ margin: 0 }}>This source is no longer available to you.</p>}
          {data && (
            <>
              <p style={{ margin: '0 0 6px', color: 'var(--muted)' }}>
                {data.document_title ?? data.citation}
                {data.page ? ` · page ${data.page}` : ''}
                {data.scope === 'private' ? ' · your private note' : ''}
                {data.read_by_ocr ? ' · read from a scan by OCR, so it may contain mistakes' : ''}
              </p>
              {data.details_label && <p style={{ margin: '0 0 6px', color: 'var(--muted)' }}>{data.details_label}</p>}
              <blockquote style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{data.text}</blockquote>
            </>
          )}
        </div>
      )}
    </div>
  );
}
