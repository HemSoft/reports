const { test, expect } = require('@playwright/test');
const path = require('node:path');
const fs = require('node:fs/promises');

const { openReport, root } = require('./fixture');

test('generated report initializes charts and supports table navigation offline', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await openReport(page);
  await expect.poll(() => page.evaluate(() => THREE.REVISION)).toBe('186');
  expect(await page.evaluate(() => typeof THREE.OrbitControls)).toBe('function');
  await expect(page.locator('canvas')).toHaveCount(9);
  await expect.poll(() => page.evaluate(() => Object.keys(Chart.instances).length)).toBe(7);
  await expect.poll(() => page.evaluate(() => [velRenderer.info.render.calls, cadRenderer.info.render.calls].every(n => n > 0))).toBe(true);
  const metrics = JSON.parse(await fs.readFile(path.join(root, 'test-results/metrics.json'), 'utf8'));
  await expect(page.locator('#pane-repos tbody tr')).toHaveCount(metrics.repo_profiles.length);
  await page.getByRole('tab', { name: /Recent Pull Requests/ }).click();
  await expect(page.locator('#pane-prs')).toBeVisible();
  await page.locator('#table-search').fill('not-a-real-fixture-value');
  await expect(page.locator('#pane-prs tbody tr:visible')).toHaveCount(0);
  await page.locator('#table-search').fill('');
  await expect(page.locator('#pane-prs tbody tr:visible')).toHaveCount(metrics.recent_prs.length);
  await page.getByRole('tab', { name: /Recent Commits/ }).click();
  await expect(page.locator('#pane-commits')).toBeVisible();
  await expect(page.locator('#pane-commits tbody tr')).toHaveCount(metrics.recent_commits.length);
  expect(errors).toEqual([]);
});

test('organization repository and commit links retain canonical owner alongside personal sources', async ({ page }) => {
  await openReport(page, { reportPath: path.join(root, 'test-results/report-organization.html') });
  await expect(page.locator('#pane-repos a', { hasText: 'hs-buddy' })).toHaveAttribute('href', 'https://github.com/hemsoft-dev/hs-buddy');
  await expect(page.locator('#pane-repos a', { hasText: 'retained' })).toHaveAttribute('href', 'https://github.com/HemSoft/retained');
  await page.getByRole('tab', { name: /Recent Commits/ }).click();
  await expect(page.locator('#pane-commits')).toBeVisible();
  await expect(page.locator('#pane-commits a[href^="https://github.com/hemsoft-dev/hs-buddy/commit/"]')).toHaveCount(2);
  await expect(page.locator('#pane-commits a[href^="https://github.com/HemSoft/retained/commit/"]')).toHaveCount(1);
  await expect(page.locator('#pane-commits a[href^="https://github.com/HemSoft/hs-buddy/commit/"]')).toHaveCount(0);
});
