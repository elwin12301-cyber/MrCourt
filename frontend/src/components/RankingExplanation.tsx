import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { type QuestionRanking, getQuestionRanking } from '../services/ranking';

const TYPE_WORDS: Record<string, string> = {
  law: 'What the law says',
  courts: 'How courts decided',
  my_case: 'About the advocate’s own case',
  other: 'General',
};

const pct = (value: number | null) => (value === null ? '–' : `${Math.round(value * 100)}`);

function Body({ data }: { data: QuestionRanking }) {
  if (!data.recorded)
    return <p>Not recorded for this answer (it was made before ranking explanations existed).</p>;
  return (
    <>
      <p>
        Kind of question: {TYPE_WORDS[data.question_type ?? 'other'] ?? 'General'}
        {data.references.length > 0 && <> · Named in the question: {data.references.join(', ')}</>}
      </p>
      {data.passages.length === 0 ? (
        <p>No source passed the checks, so none was cited.</p>
      ) : (
        <ol className="rankexp">
          {data.passages.map((p) => (
            <li key={p.position}>
              <b>{p.hidden ? 'Private document of another user' : p.label}</b>
              {p.pinned && <span className="badge">Named</span>}
              <span className="fine">
                Overall {pct(p.scores.combined)} · word match {pct(p.scores.keyword)} · meaning{' '}
                {pct(p.scores.meaning)} · answer check {pct(p.scores.rerank)}
              </span>
              {p.signals.length > 0 && (
                <span className="fine">
                  {p.signals
                    .map((s) =>
                      typeof s.value === 'number' ? `${s.label} (+${pct(s.value)})` : s.label,
                    )
                    .join(' · ')}
                </span>
              )}
            </li>
          ))}
        </ol>
      )}
    </>
  );
}

/** Administrators only: why each source of this answer ranked where it did. Loaded when opened. */
export function RankingExplanation({ questionId }: { questionId: string }) {
  const [open, setOpen] = useState(false);
  const query = useQuery({
    queryKey: ['ranking', questionId],
    queryFn: () => getQuestionRanking(questionId),
    enabled: open,
  });
  return (
    <details className="explain" onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary>Why these sources?</summary>
      {query.isLoading && <p>Loading…</p>}
      {query.isError && <p role="alert">Could not load the explanation.</p>}
      {query.data && <Body data={query.data} />}
    </details>
  );
}
