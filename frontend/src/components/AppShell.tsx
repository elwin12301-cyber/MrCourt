import { useEffect } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { useMe } from '../services/auth';
import { useClientUpdates } from '../services/client';
import { toggleTheme, type Theme, applyTheme } from '../services/theme';
import { Icon } from './Icon';
import type { IconName } from './sprite';

interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  advocateOnly?: boolean;
  clientOnly?: boolean;
  /** Wording for clients, who see their own cases rather than a caseload. */
  clientLabel?: string;
}

const NAV: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: 'home' },
  { to: '/cases', label: 'Cases', icon: 'case', clientLabel: 'My cases' },
  { to: '/updates', label: 'Updates', icon: 'cal', clientOnly: true },
  { to: '/ask', label: 'Ask MrCourt', icon: 'chat' },
  { to: '/drafts', label: 'Drafts', icon: 'file', advocateOnly: true },
  { to: '/settings', label: 'Settings', icon: 'user' },
];

/** Administrators get a menu of their own and none of the advocate or client screens. */
const ADMIN_NAV: NavItem[] = [
  { to: '/dashboard', label: 'Overview', icon: 'home' },
  { to: '/admin/advocates', label: 'Advocates', icon: 'case' },
  { to: '/admin/clients', label: 'Clients', icon: 'user' },
  { to: '/admin/cases', label: 'Cases', icon: 'file' },
  { to: '/admin/verifications', label: 'Verifications', icon: 'check' },
  { to: '/ask', label: 'Ask MrCourt', icon: 'chat' },
  { to: '/admin/messages', label: 'Messages', icon: 'chat' },
  { to: '/admin/audit', label: 'Audit log', icon: 'shield' },
  { to: '/settings', label: 'Settings', icon: 'cal' },
];

const ROLE_LABEL = { advocate: 'Advocate', petitioner: 'Petitioner', admin: 'Administrator' } as const;

export function initials(fullName: string): string {
  const words = fullName
    .split(/\s+/)
    .filter((w) => w && !/^adv\.?$/i.test(w));
  return ((words[0]?.[0] ?? '') + (words.length > 1 ? words[words.length - 1][0] : '')).toUpperCase();
}

export function AppShell() {
  const { data: me } = useMe();
  const { pathname } = useLocation();
  const savedTheme = me?.settings.theme;
  const { data: updates } = useClientUpdates(me?.role === 'petitioner');
  const unread = updates?.unread_count ?? 0;

  // A theme chosen on another device applies here too, unless this browser already has a choice.
  useEffect(() => {
    if (!savedTheme || savedTheme === 'system') return;
    let local: string | null = null;
    try {
      local = localStorage.getItem('mrcourt-theme');
    } catch {
      /* storage unavailable */
    }
    if (!local) applyTheme(savedTheme as Theme);
  }, [savedTheme]);

  if (!me) return null;

  const isClient = me.role === 'petitioner';
  const items =
    me.role === 'admin'
      ? ADMIN_NAV
      : NAV.filter((item) => (!item.advocateOnly || !isClient) && (!item.clientOnly || isClient)).map(
          (item) => ({ ...item, label: (isClient && item.clientLabel) || item.label }),
        );
  const current = (to: string) => pathname === to || pathname.startsWith(`${to}/`);

  return (
    <div className="shell" id="app">
      <aside className="side">
        <div className="logo">
          <Icon name="scale" size={28} />
          <b>MrCourt</b>
        </div>
        <nav aria-label="Main" style={{ display: 'contents' }}>
          {items.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="nav"
              aria-label={item.to === '/updates' && unread > 0 ? `${item.label}, ${unread} unread` : item.label}
              aria-current={current(item.to) ? 'page' : undefined}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
              {item.to === '/updates' && unread > 0 && <b className="badge">{unread}</b>}
            </Link>
          ))}
        </nav>
        <div className="grow" />
        <div className="user">
          <div className="avatar">{initials(me.full_name)}</div>
          <div>
            <b>{me.full_name}</b>
            <small>{ROLE_LABEL[me.role]}</small>
          </div>
        </div>
        <button type="button" className="theme" id="themeBtn" onClick={toggleTheme}>
          Toggle light / dark
        </button>
      </aside>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
