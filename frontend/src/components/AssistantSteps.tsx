import type { Step } from '../services/assistant';

const MARK: Record<Step['status'], string> = { ok: 'Done', refused: 'Not allowed', failed: 'Failed' };

/** The steps the assistant took, in order, so the person can see how the reply was reached. */
export function AssistantSteps({ steps }: { steps: Step[] }) {
  if (steps.length === 0) return null;
  return (
    <div className="steps">
      <div className="eyebrow">What I did</div>
      <ol aria-label="Steps taken">
        {steps.map((s, i) => (
          <li key={i} className={s.status === 'ok' ? '' : 'bad'}>
            {s.label}
            {s.detail ? <small> · {s.detail}</small> : null}
            {s.status !== 'ok' && <small> · {MARK[s.status]}</small>}
          </li>
        ))}
      </ol>
    </div>
  );
}
