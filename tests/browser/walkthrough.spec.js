const { test, expect } = require('@playwright/test');
const { openReport } = require('./fixture');
test.use({ video: { mode: 'on', size: { width: 1440, height: 1000 } } });
test('blocked 3D libraries show notices while charts and filtering work', async ({ page }) => {
  await openReport(page, { block: url => /three|OrbitControls/.test(url) });
  await page.locator('#viewport-velocity').scrollIntoViewIfNeeded();
  await expect(page.locator('.three-viewport [role="status"]')).toHaveCount(2);
  await page.screenshot({ path: 'test-results/fallback-notices.png' });
  await page.waitForTimeout(2300);
  await page.locator('#chart-weekly-combo').scrollIntoViewIfNeeded();
  await expect.poll(() => page.evaluate(() => Object.keys(Chart.instances).length)).toBe(7);
  await page.waitForTimeout(1200);
  await page.getByRole('button', { name: /Recent Pull Requests/ }).click();
  await page.locator('#table-search').pressSequentially('no-fixture-match', { delay: 90 });
  await expect(page.locator('#pane-prs tbody tr:visible')).toHaveCount(0);
  await page.waitForTimeout(900);
  await page.locator('#table-search').fill('');
  await expect(page.locator('#pane-prs tbody tr:visible')).toHaveCount(1);
  await page.waitForTimeout(900);
});

