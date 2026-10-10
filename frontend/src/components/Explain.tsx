import { useGlossary } from '../services/client';

/** "What does this mean?" disclosure for a legal term, using the plain-language glossary. */
export function Explain({ term }: { term: string }) {
  const { data } = useGlossary();
  const entry = data?.find((t) => t.term.toLowerCase() === term.toLowerCase());
  if (!entry) return null;
  return (
    <details className="explain">
      <summary>What does “{entry.term}” mean?</summary>
      <p>{entry.meaning}</p>
    </details>
  );
}
