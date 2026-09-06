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
  await page.getByRole('tab', { name: /Recent Pull Requests/ }).click();
  await page.locator('#table-search').pressSequentially('no-fixture-match', { delay: 90 });
  await expect(page.locator('#pane-prs tbody tr:visible')).toHaveCount(0);
  await page.waitForTimeout(900);
  await page.locator('#table-search').fill('');
  await expect(page.locator('#pane-prs tbody tr:visible')).toHaveCount(1);
  await page.waitForTimeout(900);
});

test('keyboard walkthrough exposes weekly values, cadence cells and tab state', async ({ page }) => {
  await openReport(page);
  const weekly = page.locator('#data-velocity summary');
  await weekly.focus();
  await page.keyboard.press('Enter');
  await page.locator('#data-velocity table').scrollIntoViewIfNeeded();
  await expect(page.locator('#data-velocity table')).toBeVisible();
  await page.waitForTimeout(1700);
  const cadence = page.locator('#data-cadence summary');
  await cadence.focus();
  await page.keyboard.press('Enter');
  await page.locator('#data-cadence .table-wrap').focus();
  await page.locator('#data-cadence table').scrollIntoViewIfNeeded();
  await page.screenshot({ path: 'test-results/accessible-data.png' });
  await page.waitForTimeout(1200);
  for (let index = 0; index < 16; index++) {
    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(60);
  }
  await page.waitForTimeout(1200);
  await page.getByRole('tab', { name: /Repositories/ }).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab', { name: /Recent Pull Requests/ })).toHaveAttribute('aria-selected', 'true');
  await page.waitForTimeout(1200);
});

