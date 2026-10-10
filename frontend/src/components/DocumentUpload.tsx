import { useRef, useState } from 'react';
import { ApiError } from '../services/api';
import { uploadDocument, useCaseMutation } from '../services/cases';
import { Button } from './ui';

export function DocumentUpload({ caseId }: { caseId: string }) {
  const input = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const upload = useCaseMutation((file: File) => uploadDocument(caseId, file));

  async function onPick(file: File | undefined) {
    if (!file) return;
    setError(null);
    try {
      await upload.mutateAsync(file);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Upload failed. Please try again.');
    } finally {
      if (input.current) input.current.value = '';
    }
  }

  return (
    <div style={{ marginTop: 14 }}>
      <label htmlFor="doc-file" className="fine" style={{ display: 'block', marginBottom: 6 }}>
        Add a document (PDF, image, Word or text)
      </label>
      <input
        id="doc-file"
        ref={input}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg,.doc,.docx,.txt"
        onChange={(e) => void onPick(e.target.files?.[0])}
        disabled={upload.isPending}
      />
      {error && (
        <p className="fine" role="alert" style={{ marginTop: 8 }}>
          {error}
        </p>
      )}
      {upload.isPending && (
        <Button small variant="ghost" disabled style={{ marginTop: 8 }}>
          Uploading…
        </Button>
      )}
    </div>
  );
}
