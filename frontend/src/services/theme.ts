export type Theme = 'system' | 'light' | 'dark';

const KEY = 'mrcourt-theme';

/** The classic light look is the default; a person's own choice (light, dark or "match my device") is kept. */
function readStored(): Theme {
  try {
    const value = localStorage.getItem(KEY);
    if (value === 'light' || value === 'dark' || value === 'system') return value;
  } catch {
    /* storage can be unavailable (private windows, blocked site data) */
  }
  return 'light';
}

function store(theme: Theme) {
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    /* ignore */
  }
}

export function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === 'system') delete root.dataset.theme;
  else root.dataset.theme = theme;
}

export function initTheme() {
  applyTheme(readStored());
}

export function isDark(): boolean {
  const explicit = document.documentElement.dataset.theme;
  if (explicit) return explicit === 'dark';
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

/** Flips between light and dark, mirroring the prototype's toggle. Returns the new theme. */
export function toggleTheme(): Theme {
  const next: Theme = isDark() ? 'light' : 'dark';
  applyTheme(next);
  store(next);
  return next;
}

export function setTheme(theme: Theme) {
  applyTheme(theme);
  store(theme);
}
