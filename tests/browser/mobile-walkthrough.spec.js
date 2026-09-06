const { test, expect } = require('@playwright/test');
const { openReport } = require('./fixture');

test.use({ viewport: { width: 320, height: 844 }, video: { mode: 'on', size: { width: 320, height: 844 } } });

test('mobile walkthrough keeps header, scene controls and table search reachable', async ({ page }) => {
  await openReport(page);
  await expect(page.getByRole('link', { name: 'GitHub Profile' })).toBeInViewport();
  await page.waitForTimeout(1800);
  const rotate = page.getByRole('button', { name: 'Auto-rotate weekly velocity' });
  await rotate.focus();
  await page.keyboard.press('Space');
  await expect(rotate).toHaveAttribute('aria-pressed', 'false');
  await page.waitForTimeout(1800);
  await page.locator('#data-cadence summary').focus();
  await page.keyboard.press('Enter');
  const table = page.locator('#data-cadence .table-wrap');
  await table.focus();
  for (let step = 0; step < 12; step++) {
    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(80);
  }
  await expect.poll(() => table.evaluate(element => element.scrollLeft)).toBeGreaterThan(0);
  await page.waitForTimeout(1200);
  await page.getByRole('tab', { name: /Repositories/ }).focus();
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('Tab');
  await expect(page.locator('#table-search')).toBeFocused();
  await page.locator('#table-search').pressSequentially('no-fixture-match', { delay: 70 });
  await expect(page.locator('#pane-prs tbody tr:visible')).toHaveCount(0);
  await page.waitForTimeout(1000);
  await page.locator('#table-search').fill('');
  await expect(page.locator('#pane-prs tbody tr:visible')).toHaveCount(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(320);
  await page.waitForTimeout(1000);
});
