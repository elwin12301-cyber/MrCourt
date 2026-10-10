import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiError } from '../services/api';
import { type ProposedAction as Proposal, confirmAction, declineAction } from '../services/assistant';
import { Button } from './ui';

type State = 'waiting' | 'working' | 'done' | 'declined' | 'expired' | 'error';

/** Nothing the assistant proposes happens until the person presses Confirm. */
export function ProposedActionCard({ proposal }: { proposal: Proposal }) {
  const [state, setState] = useState<State>('waiting');

  async function run(action: 'confirm' | 'decline') {
    setState('working');
    try {
      if (action === 'confirm') {
        await confirmAction(proposal.id);
        setState('done');
      } else {
        await declineAction(proposal.id);
        setState('declined');
      }
    } catch (e) {
      setState(e instanceof ApiError && e.status === 410 ? 'expired' : 'error');
    }
  }

  return (
    <div className="proposal" role="group" aria-label="Proposed action">
      <div className="eyebrow">Needs your confirmation</div>
      <p style={{ margin: '4px 0 10px' }}>{proposal.summary}</p>
      {(state === 'waiting' || state === 'working') && (
        <div style={{ display: 'flex', gap: 10 }}>
          <Button small disabled={state === 'working'} onClick={() => void run('confirm')}>
            Confirm
          </Button>
          <Button small variant="ghost" disabled={state === 'working'} onClick={() => void run('decline')}>
            Decline
          </Button>
        </div>
      )}
      <div role="status" aria-live="polite">
        {state === 'done' && (
          <p style={{ margin: 0 }}>
            Done. The draft is in <Link to="/drafts">Drafts</Link>, ready to edit. Please review it before use.
          </p>
        )}
        {state === 'declined' && <p style={{ margin: 0 }}>Declined. Nothing was created.</p>}
        {state === 'expired' && <p style={{ margin: 0 }}>This proposal has expired. Ask again if you still want it.</p>}
        {state === 'error' && <p style={{ margin: 0 }}>That did not work and nothing was changed. Please try again.</p>}
      </div>
    </div>
  );
}
