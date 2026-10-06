const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const path = require('node:path');
const fs = require('node:fs');

const site = path.resolve(__dirname, '../../test-results/landing');
const url = 'http://reports.test/landing/';

async function serveFixture(page) {
  await page.route('http://reports.test/**', async route => {
    let pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith('/')) pathname += 'index.html';
    const file = path.join(path.dirname(site), pathname);
    await route.fulfill({
      body: fs.readFileSync(file),
      contentType: file.endsWith('.json') ? 'application/json' : 'text/html',
    });
  });
}


test('report directory fits small screens, exposes table headers and works offline', async ({ browser }, testInfo) => {
  const context = await browser.newContext({ offline: true });
  const page = await context.newPage();
  await serveFixture(page);
  await page.goto(url);
  const table = page.getByRole('table', { name: 'Available reports' });
  await expect(table.getByRole('columnheader')).toHaveText(['Name', 'Link', 'Date created']);
  await expect(table.getByRole('rowheader')).toHaveText([
    'Dune: Awakening loot reference', 'Engineering Productivity Audit',
  ]);
  await expect(table.getByRole('row').nth(2)).toContainText('Sep 05, 2026');
  await expect(page.locator('script, link[rel="stylesheet"]')).toHaveCount(0);

  for (const [width, height] of [[1440, 900], [390, 844], [320, 844]]) {
    await page.setViewportSize({ width, height });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    const bounds = await table.boundingBox();
    expect(bounds.x).toBeGreaterThanOrEqual(0);
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(width);
    await page.screenshot({ path: testInfo.outputPath(`directory-${width}.png`) });
    await page.locator('summary').click();
    await expect(page.getByRole('table', { name: 'All published editions' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    await page.screenshot({ path: testInfo.outputPath(`archive-${width}.png`) });
    await page.locator('summary').click();
  }
  const scan = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(scan.violations).toEqual([]);
  await context.close();
});

test('keyboard opens latest report, older edition and archive JSON', async ({ browser }, testInfo) => {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    recordVideo: { dir: testInfo.outputDir, size: { width: 1440, height: 900 } },
  });
  const page = await context.newPage();
  await serveFixture(page);
  try {
    await page.goto(url);
    // Short pauses make the validation recording readable.
    await page.waitForTimeout(900);
    await page.keyboard.press('Tab');
    await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.locator('#main')).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(page.getByRole('link', { name: 'Open Dune: Awakening loot reference' })).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(page.getByRole('link', { name: 'Open Engineering Productivity Audit' })).toBeFocused();
    await page.waitForTimeout(600);
    await page.keyboard.press('Enter');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Snapshot 2026-09-07');
    await page.waitForTimeout(800);
    await page.getByRole('link', { name: 'All reports', exact: true }).click();
    await page.locator('summary').focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('#archive')).toHaveAttribute('open', '');
    const old = page.getByRole('link', { name: 'Snapshot 2026-09-05', exact: true });
    await expect(old).toBeVisible();
    await page.waitForTimeout(900);
    await old.click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Snapshot 2026-09-05');
    await page.waitForTimeout(800);
    await page.getByRole('link', { name: 'All reports', exact: true }).click();
    await page.locator('summary').click();
    const json = page.getByRole('link', { name: 'Engineering Productivity Audit: Snapshot 2026-09-05 data (JSON)', exact: true });
    await expect(json).toHaveAttribute('href', 'reports/productivity/2026-09-05/payload.json');
    await page.waitForTimeout(800);
    await json.click();
    expect(page.url()).toContain('/2026-09-05/payload.json');
    await expect(page.locator('body')).toContainText('total_commits');
    await page.waitForTimeout(800);
  } finally {
    await context.close();
  }
});

test('empty catalog shows a readable table message', async ({ page }) => {
  await serveFixture(page);
  await page.goto('http://reports.test/landing-empty/');
  await expect(page.getByRole('table', { name: 'Available reports' })).toContainText('No reports have been published yet.');
  await expect(page.locator('.count')).toHaveText('0 reports · 0 editions');
  await expect(page.locator('summary')).toHaveCount(0);
  const scan = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(scan.violations).toEqual([]);
});
