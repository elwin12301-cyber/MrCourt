import { useNavigate, useLocation, Route, Routes } from 'react-router-dom';
import { Icon } from '../components/Icon';
import type { IconName } from '../components/sprite';
import AskTab from './ask/AskTab';
import HistoryTab from './ask/HistoryTab';
import KnowledgeTab from './ask/KnowledgeTab';
import TextAssistantTab from './ask/TextAssistantTab';

const TABS: { id: string; label: string; path: string; icon: IconName; about: string }[] = [
  {
    id: 'ask',
    label: 'AI Assistant',
    path: '/ask',
    icon: 'chat',
    about: 'Ask a legal question. Answers cite their sources; if no reliable source is found, MrCourt says so.',
  },
  {
    id: 'knowledge',
    label: 'Knowledge Base',
    path: '/ask/knowledge',
    icon: 'file',
    about: 'The sources behind every answer. Shared sources are managed by administrators; advocates add private notes.',
  },
  {
    id: 'text',
    label: 'Text Assistant',
    path: '/ask/text',
    icon: 'mic',
    about: 'Speak or type a conversation, keep it, download it, or add it to the knowledge base.',
  },
  {
    id: 'history',
    label: 'History',
    path: '/ask/history',
    icon: 'cal',
    about: 'Every question you have asked — search it, open the conversation, or ask again.',
  },
];

/** The Knowledge Assistant: the same page and tabs for advocates, clients and administrators. */
export default function Ask() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const active = TABS.find((t) => t.path !== '/ask' && pathname.startsWith(t.path)) ?? TABS[0];

  return (
    <section className="view" id="ask" data-view="ask">
      <div className="ka-head">
        <div>
          <h1>Knowledge Assistant</h1>
          <p className="sub">{active.about}</p>
        </div>
        <span className="secure" title="Answers use only the sources you are allowed to see">
          Secure retrieval active
        </span>
      </div>
      <div className="tabs icons" role="tablist" aria-label="Knowledge Assistant sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`ask-tab-${t.id}`}
            aria-selected={active.id === t.id}
            aria-controls="ask-panel"
            tabIndex={active.id === t.id ? 0 : -1}
            onClick={() => navigate(t.path)}
            onKeyDown={(e) => {
              if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
              const i = TABS.findIndex((x) => x.id === active.id);
              const next = TABS[(i + (e.key === 'ArrowRight' ? 1 : TABS.length - 1)) % TABS.length];
              navigate(next.path);
              requestAnimationFrame(() => document.getElementById(`ask-tab-${next.id}`)?.focus());
            }}
          >
            <Icon name={t.icon} size={16} />
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id="ask-panel" aria-labelledby={`ask-tab-${active.id}`} className="stack">
        <Routes>
          <Route index element={<AskTab />} />
          <Route path="knowledge" element={<KnowledgeTab />} />
          <Route path="text" element={<TextAssistantTab />} />
          <Route path="history" element={<HistoryTab />} />
        </Routes>
      </div>
    </section>
  );
}
