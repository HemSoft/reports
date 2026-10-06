const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const edition = path.resolve(__dirname, '../../editions/dune-awakening/2026-10-05');
const url = pathToFileURL(path.join(edition, 'report.html')).href;
const data = JSON.parse(fs.readFileSync(path.join(edition, 'payload.json'), 'utf8').replace(/^\uFEFF/, ''));

test('static loot snapshot works offline with combined filters and station links', async ({ browser }) => {
  const context = await browser.newContext({ offline: true });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(url);
  await expect(page.locator('#status')).toHaveText('192 items · 5 stations + Old Quarry');
  await expect(page.locator('#station-24 tbody tr')).toHaveCount(60);

  await page.getByLabel('Find an item or station').fill('195');
  await expect(page.locator('#status')).toHaveText('68 matching items · 1 locations');
  await expect(page.locator('.station-group')).toHaveCount(1);
  await page.getByRole('button', { name: 'Reset filters' }).click();
  await page.getByLabel('Item type', { exact: true }).selectOption('Augment');
  await page.getByLabel('Community tier', { exact: true }).selectOption('S');
  const count = data.items.filter(item => item.category === 'Augment' && item.tier === 'S').length;
  await expect(page.locator('#status')).toContainText(`${count} matching items`);
  await expect(page.locator('#tiers tbody tr')).toHaveCount(count);
  await page.getByLabel('Show drop rates').check();
  await expect(page.locator('.rate-cell').first()).toBeVisible();
  await page.getByRole('button', { name: 'Reset filters' }).click();

  await page.getByLabel('Find an item or station').fill('JABAL Spitdart Ranger');
  await expect(page.locator('#status')).toHaveText('1 matching items · 1 locations');
  await expect(page.locator('#stations')).toContainText('JABAL Spitdart Focuser');
  await page.getByLabel('Find an item or station').fill('no-such-schematic');
  await expect(page.getByText('No loot matches these filters.')).toBeVisible();
  await page.getByRole('button', { name: 'Clear filters' }).first().click();
  await page.locator('#tier-S .place').first().click();
  await expect(page.locator(page.url().slice(page.url().indexOf('#')))).toHaveAttribute('open', '');
  await expect(page.getByRole('link', { name: 'All reports', exact: true })).toHaveAttribute('href', '../../../');
  expect(errors).toEqual([]);
  await context.close();
});

test('branded report is accessible and fits desktop and mobile viewports', async ({ page }, testInfo) => {
  await page.goto(url);
  await page.evaluate(() => document.fonts.ready);
  for (const width of [1440, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Dune: Awakening');
    const scan = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
    expect(scan.violations).toEqual([]);
    if (width === 1440 || width === 390) {
      await page.screenshot({ path: testInfo.outputPath(`dune-${width}.png`), fullPage: false });
    }
  }
  await page.getByLabel('Find an item or station').focus();
  await page.keyboard.type('Blade');
  await page.keyboard.press('Escape');
  await expect(page.getByLabel('Find an item or station')).toHaveValue('');
  await page.evaluate(() => window.dispatchEvent(new Event('beforeprint')));
  expect(await page.locator('details:not([open])').count()).toBe(0);
  await page.evaluate(() => window.dispatchEvent(new Event('afterprint')));
  await expect(page.locator('#sources')).not.toHaveAttribute('open', '');
});
