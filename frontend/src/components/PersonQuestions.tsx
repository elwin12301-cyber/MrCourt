import { useState } from 'react';
import { usePersonQuestions } from '../services/admin';
import { Button, Chip } from './ui';

/** What a person has asked, for the administrator. Showing it is recorded in the audit log. */
export function PersonQuestions({ userId }: { userId: string }) {
  const [shown, setShown] = useState(false);
  const { data, isError, isLoading } = usePersonQuestions(userId, shown);
  return (
    <div className="card" id="person-questions">
      <h2 style={{ marginBottom: 10 }}>Questions asked</h2>
      {!shown ? (
        <>
          <p className="fine" style={{ marginTop: 0 }}>
            Showing the questions this person has asked is recorded in the audit log. Answers are not shown.
          </p>
          <Button variant="ghost" onClick={() => setShown(true)}>
            Show questions asked
          </Button>
        </>
      ) : (
        <>
          {isLoading && <p className="sub">Loading…</p>}
          {isError && <p className="sub">Could not load the questions. Please try again.</p>}
          {data?.items.length === 0 && <p className="sub">No questions asked.</p>}
          <ul style={{ listStyle: 'none', margin: 0, padding: 0 }} aria-label="Questions asked">
            {data?.items.map((q) => (
              <li className="act" key={q.id}>
                <span>
                  <b>{q.text}</b>
                  <small style={{ display: 'block' }}>
                    {new Date(q.created_at).toLocaleString('en-IN')} · {q.mode === 'assistant' ? 'Assistant' : 'Answer'} ·{' '}
                    {q.input_method === 'voice' ? 'Voice' : 'Typed'}
                  </small>
                </span>
                <Chip tone={q.outcome_label === 'Answered' ? 'ok' : 'closed'}>{q.outcome_label}</Chip>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
