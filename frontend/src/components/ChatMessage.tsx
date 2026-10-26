import { Link } from 'react-router-dom';
import type { AssistantReply } from '../services/assistant';
import { useMe } from '../services/auth';
import type { Answer } from '../services/questions';
import { AssistantSteps } from './AssistantSteps';
import { Icon } from './Icon';
import { CitedSource } from './PassageViewer';
import { ProposedActionCard } from './ProposedAction';
import { RankingExplanation } from './RankingExplanation';
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
  const me = useMe().data;
  return (
    // data-voice-read: "read the answer" reads this whole card, with its sources and the disclaimer.
    <div className="card a" data-voice-read>
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
          {answer.message && (
            <p className="fine" role="note" style={{ fontWeight: 600 }}>
              {answer.message}
            </p>
          )}
          {answer.paragraphs.map((p, i) => (
            <p key={i}>
              {p.text} {p.citation_numbers.map((n) => `[${n}]`).join('')}
            </p>
          ))}
          {answer.citations.map((c) => (
            <CitedSource key={c.number} number={c.number} label={c.label} passageId={c.passage_id} details={c.details} />
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
      {me?.is_admin && !reply && answer.question_id && <RankingExplanation questionId={answer.question_id} />}
      <Disclaimer text={answer.disclaimer} />
      {answer.lawyer_reminder && <p className="fine" style={{ margin: '6px 0 0' }}>{answer.lawyer_reminder}</p>}
    </div>
  );
}
