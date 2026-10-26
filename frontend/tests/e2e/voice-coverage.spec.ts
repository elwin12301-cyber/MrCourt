import type { Page } from '@playwright/test';
import { expect, test } from './support/test';
import { signInAs } from './support/helpers';

/**
 * US6: everything clickable on every main screen can be reached by voice, and it stays that way (FR-022, SC-008).
 * Visits the screens of each role, uses the same control scan the app uses, and fails on:
 *   - a visible clickable control with no accessible name;
 *   - an element that looks clickable (pointer cursor) but is not a control voice can reach (mouse-only);
 *   - a control with a risky word in its name that is not tagged data-voice-risk (tag it, or tag it "none" if safe);
 *   - two controls on one screen with the same name and kind that cannot be told apart by their place in a list.
 */

interface Seen {
  name: string;
  kind: string;
  risky: boolean;
  riskKind: string;
  tagged: boolean;
  enabled: boolean;
  group: string;
  inRepeat: boolean;
}
interface Coverage {
  controls: Seen[];
  mouseOnly: string[];
  unnamed: string[];
}

async function coverage(page: Page): Promise<Coverage> {
  return page.evaluate(() => (window as unknown as { __voiceCoverage: () => Coverage }).__voiceCoverage());
}

async function settle(page: Page) {
  await page.waitForLoadState('networkidle').catch(() => undefined);
  await page.waitForTimeout(250);
}

const findings: string[] = [];

async function check(page: Page, label: string) {
  await settle(page);
  const c = await coverage(page);
  for (const name of c.unnamed) findings.push(`${label}: a clickable control has no name: ${name}`);
  for (const item of c.mouseOnly) findings.push(`${label}: mouse-only clickable (voice cannot reach it): ${item}`);
  for (const control of c.controls) {
    if (control.risky && !control.tagged) {
      findings.push(`${label}: “${control.name}” has a risky word but no data-voice-risk tag (tag it, or use "none")`);
    }
  }
  const seen = new Map<string, number>();
  for (const control of c.controls.filter((x) => !x.inRepeat)) {
    const key = `${control.kind}|${control.name.toLowerCase()}|${control.group}`;
    seen.set(key, (seen.get(key) ?? 0) + 1);
  }
  for (const [key, count] of seen) {
    const [kind, name, group] = key.split('|');
    if (count > 1) findings.push(`${label}: ${count} controls named “${name}” (${kind}${group ? ` in “${group}”` : ''}): give them distinct names or a list`);
  }
  return c;
}

async function visit(page: Page, path: string) {
  await page.goto(path);
  await expect(page.locator('main')).toBeVisible();
  return check(page, path);
}

async function openFirst(page: Page, listPath: string, rowSelector: string, label: string) {
  await page.goto(listPath);
  await settle(page);
  const row = page.locator(rowSelector).first();
  if (await row.count()) {
    await row.click();
    await page.waitForURL((url) => url.pathname !== listPath, { timeout: 8000 }).catch(() => undefined);
    await check(page, label);
  }
}

test.afterEach(() => {
  expect(findings, `\n${[...new Set(findings)].join('\n')}`).toEqual([]);
});

test('advocate screens', async ({ page }) => {
  findings.length = 0;
  await signInAs(page, 'rohan.sharma@example.com');
  for (const path of ['/dashboard', '/cases', '/ask', '/ask/knowledge', '/ask/text', '/ask/history', '/drafts', '/settings']) {
    await visit(page, path);
  }
  await openFirst(page, '/cases', 'tbody tr[tabindex="0"]', 'advocate case page');
});

test('client screens', async ({ page }) => {
  findings.length = 0;
  await signInAs(page, 'anita.sharma@example.com');
  for (const path of ['/dashboard', '/cases', '/updates', '/ask', '/ask/knowledge', '/ask/history', '/settings']) {
    await visit(page, path);
  }
  await openFirst(page, '/cases', 'a.clientcase', 'client case page');
});

test('administrator screens', async ({ page }) => {
  findings.length = 0;
  await signInAs(page, 'admin@example.com');
  for (const path of [
    '/dashboard', '/admin/advocates', '/admin/clients', '/admin/cases', '/admin/verifications', '/admin/messages',
    '/admin/audit', '/ask', '/ask/knowledge', '/ask/history', '/settings',
  ]) {
    await visit(page, path);
  }
  await openFirst(page, '/admin/advocates', 'tbody tr[tabindex="0"], tbody tr a', 'admin person page');
  await openFirst(page, '/admin/cases', 'tbody tr[tabindex="0"], tbody tr a', 'admin case page');
});

test.describe('the check itself', () => {
  test.beforeEach(() => {
    findings.length = 0;
  });

  test('a new labelled button is reachable by name and by number with no voice-specific code', async ({ page }) => {
    const { fakeVoice, say, turnOnVoice, voiceBar } = await import('./support/voice');
    await fakeVoice(page);
    await signInAs(page, 'rohan.sharma@example.com');
    await turnOnVoice(page);
    await page.evaluate(() => {
      const b = document.createElement('button');
      b.textContent = 'Brand new action';
      b.addEventListener('click', () => b.setAttribute('data-pressed', 'yes'));
      document.querySelector('main')?.appendChild(b);
    });
    await say(page, 'click brand new action');
    await expect(page.getByRole('button', { name: 'Brand new action' })).toHaveAttribute('data-pressed', 'yes');
    await expect(voiceBar(page)).toContainText('Pressed');
    await say(page, 'show numbers');
    await expect(page.locator('.vc-num').first()).toBeVisible();
  });

  test('a control with no name and a mouse-only element make the check fail and name them', async ({ page }) => {
    await signInAs(page, 'rohan.sharma@example.com');
    await expect(page.locator('main')).toBeVisible();
    await page.evaluate(() => {
      const main = document.querySelector('main');
      const icon = document.createElement('button');
      icon.innerHTML = '<svg aria-hidden="true" width="10" height="10"></svg>';
      icon.className = 'nameless-demo';
      main?.appendChild(icon);
      const div = document.createElement('div');
      div.textContent = 'Click me with a mouse';
      div.className = 'mouse-only-demo';
      div.style.cursor = 'pointer';
      div.addEventListener('click', () => undefined);
      main?.appendChild(div);
    });
    const c = await coverage(page);
    expect(c.unnamed.some((u) => u.includes('nameless-demo'))).toBe(true);
    expect(c.mouseOnly.some((m) => m.includes('mouse-only-demo'))).toBe(true);
  });
});
