import { afterEach, describe, expect, it } from 'vitest';
import { scanControls } from '../../src/voice/controls';
import { matchTarget } from '../../src/voice/matcher';

function page(html: string) {
  document.body.innerHTML = html;
  return scanControls();
}

afterEach(() => {
  document.body.innerHTML = '';
});

const one = (target: string, controls: ReturnType<typeof page>, preferNav = false) => {
  const found = matchTarget(target, controls, { preferNav });
  return found.kind === 'one' ? found.control.name : found.kind;
};

describe('matching a spoken target to controls', () => {
  const menu = `<nav><a href="/d">Dashboard</a><a href="/c">Cases</a><a href="/a">Ask MrCourt</a><a href="/s">Settings</a><a href="/o">Sign out</a></nav>
    <main><button>Save</button><button>Add case</button><button>Cancel</button><div role="tablist"><button role="tab">History</button><button role="tab">Ask</button></div></main>`;

  it('finds an exact name, a partial name and a name with generic words', () => {
    const c = page(menu);
    expect(one('dashboard', c)).toBe('Dashboard');
    expect(one('history', c)).toBe('History');
    expect(one('ask mrcourt', c)).toBe('Ask MrCourt');
    expect(one('add case', c)).toBe('Add case');
    expect(one('settings', c)).toBe('Settings');
  });

  it('knows other spoken forms: log out for Sign out, Tamil and Hindi names', () => {
    const c = page(menu);
    expect(one('log out', c)).toBe('Sign out');
    expect(one('டாஷ்போர்டு', c)).toBe('Dashboard');
    expect(one('सेटिंग', c)).toBe('Settings');
    expect(one('வழக்குகள்', c)).toBe('Cases');
  });

  it('forgives one slip in a long word but never invents a match', () => {
    const c = page(menu);
    expect(one('dashbord', c)).toBe('Dashboard');
    expect(one('banana', c)).toBe('none');
    expect(one('sav', c)).toBe('none'); // a short word is never stretched
  });

  it('asks rather than choosing when two controls fit equally well', () => {
    const c = page('<button>Save</button><button>Save</button>');
    const found = matchTarget('save', c);
    expect(found.kind).toBe('several');
    if (found.kind === 'several') expect(found.controls).toHaveLength(2);
  });

  it('a menu item beats a button of the same name for "go to", only when asked to prefer it', () => {
    const c = page('<nav><a href="/s">Settings</a></nav><main><button>Settings</button></main>');
    expect(matchTarget('settings', c).kind).toBe('several');
    expect(one('settings', c, true)).toBe('Settings');
    const found = matchTarget('settings', c, { preferNav: true });
    expect(found.kind === 'one' && found.control.isNav).toBe(true);
  });

  it('prefers an enabled control; a disabled one is returned only when nothing enabled fits', () => {
    const c = page('<button disabled>Send</button><button>Send update</button>');
    expect(one('send', c)).toBe('Send update');
    const d = page('<button disabled>Send</button>');
    const found = matchTarget('send', d);
    expect(found.kind === 'one' && found.control.enabled).toBe(false);
  });

  it('gives the closest names when nothing matches', () => {
    const c = page(menu);
    const found = matchTarget('case history', c);
    expect(found.kind === 'none' || found.kind === 'one' || found.kind === 'several').toBe(true);
    const none = matchTarget('zzz', c);
    expect(none).toEqual({ kind: 'none', closest: [] });
  });

  it('an empty target matches nothing', () => {
    expect(matchTarget('', page(menu))).toEqual({ kind: 'none', closest: [] });
  });
});
