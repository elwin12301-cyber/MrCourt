import { expect, test } from './support/test';
import { createClientScenario } from './support/helpers';

// A 1x1 PNG: the fake OCR engine in the end-to-end server returns fixed text for any image.
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
  'base64',
);

test('a scanned image is read by OCR, marked as such, found by a question, and its source shows the marking', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    const p = s.advocate;
    await p.goto('/ask/knowledge');
    await p.getByRole('button', { name: 'Add a private note' }).click();
    const title = `Scanned notice ${Date.now()}`;
    await p.getByLabel('Title').fill(title);
    await p.getByLabel('Citation (shown in answers)').fill(`Scanned Notice ${Date.now()}`);
    await p.getByLabel('File (PDF, text or scanned image)').setInputFiles({ name: 'notice.png', mimeType: 'image/png', buffer: PNG });
    await p.getByRole('button', { name: 'Add source' }).click();

    const row = p.locator('tbody tr', { hasText: title });
    await expect(row).toContainText('Ready');
    await expect(row).toContainText('1 page read by OCR');

    await p.getByRole('tab', { name: 'AI Assistant' }).click();
    await p.getByLabel('Ask a legal question').fill('How many days does the zorvex scanned notice give to reply?');
    await p.getByRole('button', { name: 'Send' }).click();
    const answer = p.locator('.card.a').last();
    await expect(answer.locator('.src')).toContainText('Scanned Notice');
    await answer.getByRole('button', { name: 'Read source 1' }).click();
    const source = answer.getByRole('region', { name: 'Source 1' });
    await expect(source).toContainText('eleven days to reply');
    await expect(source).toContainText('read from a scan by OCR');
  } finally {
    await s.close();
  }
});

test('the Knowledge tab accepts image files', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await s.advocate.goto('/ask/knowledge');
    await s.advocate.getByRole('button', { name: 'Add a private note' }).click();
    await expect(s.advocate.getByLabel('File (PDF, text or scanned image)')).toHaveAttribute('accept', /\.png/);
  } finally {
    await s.close();
  }
});
