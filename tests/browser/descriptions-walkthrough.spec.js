const { test, expect } = require('@playwright/test');
const { openReport } = require('./fixture');

test.use({ video: { mode: 'on', size: { width: 1440, height: 1000 } } });

test('walkthrough shows source timestamp, measured cycle percentage and selected period', async ({ page }) => {
  await openReport(page);
  await expect(page.locator('.time-badge')).toContainText('Sep 05, 2026 12:00:00 EDT (UTC-0400)');
  await expect(page.locator('.time-badge')).toContainText('America/New_York (ET)');
  await page.waitForTimeout(1600);
  const cycle = page.getByRole('region', { name: 'Pull request cycle duration', exact: true });
  await cycle.scrollIntoViewIfNeeded();
  await expect(cycle).toContainText('100.0% under 1 hour; measured merged PRs');
  await cycle.getByText('View Pull request cycle duration data', { exact: true }).click();
  await expect(cycle.getByRole('row', { name: 'Less than 1 hour 1', exact: true })).toBeVisible();
  await page.waitForTimeout(1800);
  const footer = page.locator('footer');
  await footer.scrollIntoViewIfNeeded();
  await expect(footer).toContainText('Audited Period: Aug 22, 2026 – Sep 05, 2026');
  await page.waitForTimeout(1600);
});
