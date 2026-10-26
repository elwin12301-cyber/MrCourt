import { RankingExplanation } from '../../components/RankingExplanation';
import { useDeferredValue, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnswerMessage } from '../../components/ChatMessage';
import { Icon } from '../../components/Icon';
import { Chip } from '../../components/ui';
import { useMe } from '../../services/auth';
import {
  type HistoryFilters,
  type HistoryItem,
  type WorkspaceItem,
  asReply,
  useHistory,
  useHistoryDetail,
  useWorkspaceHistory,
} from '../../services/history';

const when = (iso: string) =>
  new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });

const ASSISTANT_NAME = (item: HistoryItem) => (item.mode === 'text' ? 'Text Assistant' : 'AI Assistant');

function Opened({ id }: { id: string }) {
  const { data, isError } = useHistoryDetail(id);
  if (isError) return <p className="fine">Could not open this question. Please try again.</p>;
  if (!data) return <p className="fine">Opening…</p>;
  if (data.lines) {
    return (
      <div className="card a" data-voice-read>
        {data.conversation_deleted && (
          <p className="fine" style={{ margin: '0 0 8px' }}>
            This conversation was deleted from the Text Assistant tab. This is the text it had.
          </p>
        )}
        <ul style={{ margin: 0, paddingLeft: 18 }} aria-label="Conversation lines">
          {data.lines.map((line) => (
            <li key={line.id} style={{ whiteSpace: 'pre-wrap' }}>
              {line.text} <small>({line.source === 'voice' ? 'voice' : 'typed'})</small>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  return <AnswerMessage answer={asReply(data)} />;
}

function Row({ item, others }: { item: HistoryItem | WorkspaceItem; others: boolean }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const isText = item.mode === 'text';
  const asker = 'asker_name' in item ? item.asker_name : null;
  return (
    <li className="ka-row" style={{ flexWrap: 'wrap' }}>
      <div style={{ minWidth: 0, flex: '1 1 320px' }}>
        <b style={{ overflowWrap: 'anywhere' }}>{item.text}</b>
        <div className="ka-meta">
          {when(item.created_at)} · {ASSISTANT_NAME(item)} ·{' '}
          <Icon name={item.input_method === 'voice' ? 'mic' : 'file'} size={13} style={{ verticalAlign: '-2px' }} />{' '}
          {item.input_method === 'voice' ? 'Voice' : 'Typed'}
          {item.channel === 'whatsapp' ? ' · Asked on WhatsApp' : ''}
          {asker ? ` · ${asker}` : ''}
        </div>
      </div>
      <div className="ka-actions">
        <Chip tone={item.outcome_label === 'No information found' ? 'closed' : 'ok'}>{item.outcome_label}</Chip>
        {!others && (
          <>
            <button
              type="button"
              className="btn small outline"
              aria-expanded={open}
              aria-label={`${open ? 'Close' : 'Open'} “${item.text}”`}
              onClick={() => setOpen((v) => !v)}
            >
              {open ? 'Close' : 'Open'}
            </button>
            {!isText && (
              <button
                type="button"
                className="btn small"
                aria-label={`Ask again “${item.text}”`}
                onClick={() => navigate('/ask', { state: { question: item.text, assistant: item.mode === 'assistant' } })}
              >
                Ask again
              </button>
            )}
          </>
        )}
      </div>
      {open && !others && (
        <div style={{ flexBasis: '100%' }}>
          <Opened id={item.id} />
        </div>
      )}
      {others && item.mode === 'answer' && (
        <div style={{ flexBasis: '100%' }}>
          <RankingExplanation questionId={item.id} />
        </div>
      )}
    </li>
  );
}

/**
 * Every question the person has asked: search, filter, open, or ask again. Only they can see it.
 * Administrators can also switch to everyone's questions (a list, recorded in the audit log).
 */
export default function HistoryTab() {
  const me = useMe().data;
  const isAdmin = me?.role === 'admin';
  const [search, setSearch] = useState('');
  const [outcome, setOutcome] = useState<HistoryFilters['outcome']>('');
  const [input, setInput] = useState<HistoryFilters['input']>('');
  const [source, setSource] = useState<HistoryFilters['source']>('');
  const [everyone, setEveryone] = useState(false);
  const q = useDeferredValue(search);
  const filters = { q, outcome, input, source };
  const mine = useHistory(filters, !everyone);
  const workspace = useWorkspaceHistory(filters, isAdmin && everyone);
  const active = everyone ? workspace : mine;
  const items = active.data?.pages.flatMap((p) => p.items) ?? [];
  const filtered = Boolean(search || outcome || input || source);

  return (
    <div className="ka-card" id="history">
      <div className="ka-filters">
        <input
          className="ka-search"
          aria-label="Search your questions"
          placeholder={everyone ? 'Search everyone’s questions…' : 'Search your questions…'}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select aria-label="Filter by assistant" value={source} onChange={(e) => setSource(e.target.value as HistoryFilters['source'])}>
          <option value="">Both assistants</option>
          <option value="ask">AI Assistant</option>
          <option value="text">Text Assistant</option>
        </select>
        <select aria-label="Filter by outcome" value={outcome} onChange={(e) => setOutcome(e.target.value as HistoryFilters['outcome'])}>
          <option value="">All outcomes</option>
          <option value="answered">Answered</option>
          <option value="none">No information found</option>
        </select>
        <select aria-label="Filter by how it was asked" value={input} onChange={(e) => setInput(e.target.value as HistoryFilters['input'])}>
          <option value="">Typed or voice</option>
          <option value="typed">Typed</option>
          <option value="voice">Voice</option>
        </select>
        {isAdmin && (
          <select aria-label="Whose questions" value={everyone ? 'everyone' : 'mine'} onChange={(e) => setEveryone(e.target.value === 'everyone')}>
            <option value="mine">My questions</option>
            <option value="everyone">Everyone’s questions</option>
          </select>
        )}
      </div>
      <p className="fine" style={{ margin: '12px 0 4px' }}>
        {everyone
          ? 'Showing everyone’s questions in this workspace. Only the list is shown, not the answers, and showing it is recorded in the audit log.'
          : 'Every question you ask is kept here, even after a conversation is deleted. Only you can see them, and deleting your account removes them. Administrators can review questions asked in this workspace.'}
      </p>
      {active.isError && <p className="sub">Could not load the questions. Please try again.</p>}
      {!active.isError && !active.isLoading && items.length === 0 && (
        <p className="sub">{filtered ? 'No questions match.' : everyone ? 'No one has asked anything yet.' : 'You have not asked anything yet.'}</p>
      )}
      <ul style={{ listStyle: 'none', margin: 0, padding: 0 }} aria-label={everyone ? 'Everyone’s questions' : 'Your questions'}>
        {items.map((item) => (
          <Row key={item.id} item={item} others={everyone} />
        ))}
      </ul>
      {active.hasNextPage && (
        <div style={{ marginTop: 12 }}>
          <button type="button" className="btn small outline" disabled={active.isFetchingNextPage} onClick={() => void active.fetchNextPage()}>
            {active.isFetchingNextPage ? 'Loading…' : 'Show older questions'}
          </button>
        </div>
      )}
    </div>
  );
}
