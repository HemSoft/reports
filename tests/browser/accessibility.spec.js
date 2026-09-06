const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const fs = require('node:fs/promises');
const path = require('node:path');
const { openReport, root } = require('./fixture');

test('nine named visualizations expose complete equivalent data and accessible structure', async ({ page }) => {
  await openReport(page);
  const metrics = JSON.parse(await fs.readFile(path.join(root, 'test-results/metrics.json'), 'utf8'));
  const regions = page.locator('[data-visualization]');
  await expect(regions).toHaveCount(9);
  await expect(page.locator('canvas[role="img"][aria-label][aria-describedby]')).toHaveCount(9);
  for (const region of await regions.all()) {
    await expect(region).toHaveAccessibleName(/.+/);
    const summary = region.locator('summary');
    await summary.focus();
    await page.keyboard.press('Enter');
    await expect(region.locator('table')).toBeVisible();
  }
  let cumulative = 0;
  const weeklyRows = metrics.weekly_data.map(w => {
    cumulative += w.additions;
    return [w.label, w.start_date, w.end_date, w.commits, w.prs_opened, w.prs_merged,
      w.issues_closed, w.additions, w.deletions, w.net_lines, w.human_commits, w.ai_commits,
      w.active_days, w.top_repo, cumulative].map(String);
  });
  const expected = {
    velocity: weeklyRows,
    'weekly-combo': weeklyRows,
    cadence: metrics.temporal.day_names.map((day, index) => [day, ...metrics.temporal.matrix_7x24[index].map(String)]),
    'day-distribution': Object.entries(metrics.temporal.day_counts).map(([day, count]) => [day, String(count)]),
    'hour-distribution': Object.entries(metrics.temporal.hour_counts).map(([hour, count]) => [hour.padStart(2, '0') + ':00', String(count)]),
    'repo-share': metrics.repo_profiles.slice(0, 8).map(r => [r.name, String(r.commits)]),
    'pr-cycle': [
      ['Less than 1 hour', metrics.kpis.pr_cycle_distribution.under_1h],
      ['1 to less than 4 hours', metrics.kpis.pr_cycle_distribution['1h_to_4h']],
      ['4 to less than 24 hours', metrics.kpis.pr_cycle_distribution['4h_to_24h']],
      ['24 to less than 72 hours', metrics.kpis.pr_cycle_distribution['1d_to_3d']],
      ['72 hours or more', metrics.kpis.pr_cycle_distribution.over_3d],
    ].map(([label, count]) => [label, String(count)]),
    'commit-categories': Object.entries(metrics.category_distribution).map(([name, count]) => [name, String(count)]),
    languages: metrics.language_breakdown.slice(0, 7).map(l => [l.language, String(l.additions), String(l.deletions)]),
  };
  for (const [key, rows] of Object.entries(expected)) {
    const actual = await page.locator(`#data-${key} tbody tr`).evaluateAll(elements => elements.map(
      row => Array.from(row.children).map(cell => cell.textContent)));
    expect(actual, key).toEqual(rows);
  }
  await expect(page.locator('#data-cadence td')).toHaveCount(168);
  const matrixRegion = page.locator('#data-cadence .table-wrap');
  await matrixRegion.focus();
  await page.keyboard.press('ArrowRight');
  await expect.poll(() => matrixRegion.evaluate(element => element.scrollLeft)).toBeGreaterThan(0);
  const left = await matrixRegion.boundingBox();
  const rowHeader = await page.locator('#data-cadence tbody th').first().boundingBox();
  expect(Math.abs(rowHeader.x - left.x)).toBeLessThan(3);
  const snapshot = await page.locator('[data-visualization="cadence"]').ariaSnapshot();
  expect(snapshot).toContain('rowheader "Tuesday"');
  expect(snapshot).toContain('columnheader "23:00"');
  expect((snapshot.match(/- cell /g) || []).length).toBe(168);
  await fs.writeFile(path.join(root, 'test-results/cadence-accessibility.yml'), snapshot);
  const scan = await new AxeBuilder({ page }).include('[data-visualization]').include('.table-toolbar').analyze();
  await fs.writeFile(path.join(root, 'test-results/accessibility.json'), JSON.stringify(scan.violations, null, 2));
  expect(scan.violations).toEqual([]);
});

test('keyboard controls expose rotation, selected tabs and named search', async ({ page }) => {
  await openReport(page);
  const rotate = page.getByRole('button', { name: 'Auto-rotate weekly velocity' });
  await rotate.focus();
  await expect(rotate).toHaveAttribute('aria-pressed', 'true');
  await page.keyboard.press('Space');
  await expect(rotate).toHaveAttribute('aria-pressed', 'false');
  expect(await page.evaluate(() => velAutoRotate)).toBe(false);
  await page.keyboard.press('Enter');
  await expect(rotate).toHaveAttribute('aria-pressed', 'true');
  const tabs = page.getByRole('tablist', { name: 'Report tables' });
  await tabs.getByRole('tab', { name: /Repositories/ }).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab', { name: /Recent Pull Requests/ })).toBeFocused();
  await expect(page.getByRole('tab', { name: /Recent Pull Requests/ })).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#pane-repos')).toBeHidden();
  await page.keyboard.press('End');
  await expect(page.getByRole('tab', { name: /Recent Commits/ })).toBeFocused();
  await page.keyboard.press('Home');
  await expect(page.getByRole('tab', { name: /Repositories/ })).toBeFocused();
  await page.keyboard.press('ArrowLeft');
  await expect(page.getByRole('tab', { name: /Recent Commits/ })).toBeFocused();
  await page.keyboard.press('Tab');
  const search = page.getByRole('searchbox', { name: 'Filter the selected report table' });
  await expect(search).toBeFocused();
  await page.keyboard.type('no-fixture-match');
  await expect(page.locator('#pane-commits tbody tr:visible')).toHaveCount(0);
  await search.fill('');
  await expect(page.locator('#pane-commits tbody tr:visible')).toHaveCount(2);
});

test('data alternatives remain available when graphics dependencies fail', async ({ page }) => {
  await openReport(page, { block: url => /three|OrbitControls|chart.umd/.test(url) });
  await expect(page.locator('.visualization-fallback')).toHaveCount(9);
  for (const summary of await page.locator('.chart-data summary').all()) {
    await summary.focus();
    await page.keyboard.press('Enter');
  }
  await expect(page.locator('.chart-data table:visible')).toHaveCount(9);
  await expect(page.locator('#data-cadence td')).toHaveCount(168);
  await expect(page.getByRole('button', { name: 'Auto-rotate weekly velocity' })).toHaveAttribute('aria-pressed', 'false');
});
