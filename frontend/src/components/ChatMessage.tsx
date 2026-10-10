import { Link } from 'react-router-dom';
import type { AssistantReply } from '../services/assistant';
import type { Answer } from '../services/questions';
import { AssistantSteps } from './AssistantSteps';
import { Icon } from './Icon';
import { CitedSource } from './PassageViewer';
import { ProposedActionCard } from './ProposedAction';
import { Disclaimer } from './ui';

export function SourceChip({ number, label }: { number: number; label: string }) {
  return (
    <div className="src">
      <b>[{number}]</b>
      {label}
    </div>
  );
}

export function UserMessage({ text }: { text: string }) {
  return <div className="u">{text}</div>;
}

function Who() {
  return (
    <div className="who">
      <Icon name="scale" size={18} />
      MrCourt
    </div>
  );
}

export function PendingMessage({ assistant = false }: { assistant?: boolean }) {
  return (
    <div className="card a" role="status">
      <Who />
      <p>{assistant ? 'Working on it…' : 'Looking this up in the indexed law…'}</p>
    </div>
  );
}

export function ErrorMessage({ text }: { text: string }) {
  return (
    <div className="card a" role="alert">
      <Who />
      <p>{text}</p>
    </div>
  );
}

/** A cited answer, or the explicit "no reliable source" response. The disclaimer is always shown. */
export function AnswerMessage({ answer, askLawyerHref }: { answer: Answer | AssistantReply; askLawyerHref?: string }) {
  const reply = 'steps' in answer ? answer : null;
  return (
    <div className="card a">
      <Who />
      {answer.case_specific_notice && (
        <div className="advicenotice" role="note">
          <p>{answer.case_specific_notice}</p>
          {askLawyerHref && (
            <Link to={askLawyerHref} className="btn small ghost">
              Ask your lawyer
            </Link>
          )}
        </div>
      )}
      {reply && <AssistantSteps steps={reply.steps} />}
      {answer.outcome !== 'no_reliable_source' ? (
        <>
          {answer.paragraphs.map((p, i) => (
            <p key={i}>
              {p.text} {p.citation_numbers.map((n) => `[${n}]`).join('')}
            </p>
          ))}
          {answer.citations.map((c) => (
            <CitedSource key={c.number} number={c.number} label={c.label} passageId={c.passage_id} />
          ))}
        </>
      ) : (
        <p>{answer.message}</p>
      )}
      {answer.source_language_note && (
        <p className="fine" style={{ margin: '6px 0 0' }}>
          {answer.source_language_note}
        </p>
      )}
      {reply?.proposed_action && <ProposedActionCard proposal={reply.proposed_action} />}
      <Disclaimer text={answer.disclaimer} />
      {answer.lawyer_reminder && <p className="fine" style={{ margin: '6px 0 0' }}>{answer.lawyer_reminder}</p>}
    </div>
  );
}
