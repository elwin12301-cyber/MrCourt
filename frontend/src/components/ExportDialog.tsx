import { useState } from 'react';
import { type Draft, exportDraft } from '../services/drafts';
import { Button } from './ui';

/** Inline format chooser. Nothing is produced until the user picks Word or PDF. */
export function ExportDialog({ draft, onClose }: { draft: Draft; onClose: () => void }) {
  const [busy, setBusy] = useState<'docx' | 'pdf' | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(format: 'docx' | 'pdf') {
    setBusy(format);
    setError(null);
    try {
      await exportDraft(draft, format);
      onClose();
    } catch {
      setError('Export failed. Your draft has not been changed. Please try again.');
    } finally {
      setBusy(null);
    }
  }

  return (
    <div role="group" aria-label="Export format" style={{ marginTop: 14, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
      <span className="fine">Export as</span>
      <Button small variant="ghost" disabled={busy !== null} onClick={() => void run('docx')}>
        Word (.docx)
      </Button>
      <Button small variant="ghost" disabled={busy !== null} onClick={() => void run('pdf')}>
        PDF
      </Button>
      <Button small variant="ghost" onClick={onClose}>
        Cancel
      </Button>
      {error && (
        <p className="fine" role="alert" style={{ flexBasis: '100%', margin: 0 }}>
          {error}
        </p>
      )}
    </div>
  );
}
