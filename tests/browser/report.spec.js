const { test, expect } = require('@playwright/test');
const path = require('node:path');
const fs = require('node:fs/promises');

const root = path.resolve(__dirname, '../..');
const scripts = new Map([
  ['https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js', 'node_modules/chart.js/dist/chart.umd.js'],
  ['https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js', 'node_modules/three/build/three.min.js'],
  ['https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js', 'node_modules/three/examples/js/controls/OrbitControls.js'],
]);

test('generated report initializes charts and supports table navigation offline', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', async route => {
    const url = route.request().url();
    if (url === 'http://report.test/') {
      return route.fulfill({ path: path.join(root, 'test-results/report.html'), contentType: 'text/html' });
    }
    if (scripts.has(url)) {
      return route.fulfill({ path: path.join(root, scripts.get(url)), contentType: 'application/javascript' });
    }
    if (url.startsWith('https://fonts.googleapis.com/')) {
      return route.fulfill({ body: '', contentType: 'text/css' });
    }
    if (url.startsWith('https://avatars.githubusercontent.com/')) {
      return route.fulfill({ body: '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>', contentType: 'image/svg+xml' });
    }
    throw new Error(`Unexpected external request: ${url}`);
  });
  await page.goto('http://report.test/');
  await expect(page.locator('canvas')).toHaveCount(9);
  await expect.poll(() => page.evaluate(() => Object.keys(Chart.instances).length)).toBe(7);
  await expect.poll(() => page.evaluate(() => [velRenderer.info.render.calls, cadRenderer.info.render.calls].every(n => n > 0))).toBe(true);
  const metrics = JSON.parse(await fs.readFile(path.join(root, 'test-results/metrics.json'), 'utf8'));
  await expect(page.locator('#pane-repos tbody tr')).toHaveCount(metrics.repo_profiles.length);
  await page.getByRole('button', { name: /Recent Pull Requests/ }).click();
  await expect(page.locator('#pane-prs')).toBeVisible();
  await page.locator('#table-search').fill('not-a-real-fixture-value');
  await expect(page.locator('#pane-prs tbody tr:visible')).toHaveCount(0);
  await page.locator('#table-search').fill('');
  await expect(page.locator('#pane-prs tbody tr:visible')).toHaveCount(metrics.recent_prs.length);
  await page.getByRole('button', { name: /Recent Commits/ }).click();
  await expect(page.locator('#pane-commits')).toBeVisible();
  await expect(page.locator('#pane-commits tbody tr')).toHaveCount(metrics.recent_commits.length);
  expect(errors).toEqual([]);
});
