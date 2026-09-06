const { test, expect } = require('@playwright/test');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { openReport, root } = require('./fixture');

async function assertTablesWork(page) {
  await page.getByRole('button', { name: /Recent Pull Requests/ }).click();
  await expect(page.locator('#pane-prs')).toBeVisible();
  await expect(page.locator('#pane-prs tbody tr:visible')).toHaveCount(1);
  await page.locator('#table-search').fill('no-fixture-match');
  await expect(page.locator('#pane-prs tbody tr:visible')).toHaveCount(0);
  await page.locator('#table-search').fill('');
  await expect(page.locator('#pane-prs tbody tr:visible')).toHaveCount(1);
}

for (const scenario of ['three-blocked', 'controls-blocked', 'webgl-unavailable']) {
  test(`${scenario} preserves charts and tables`, async ({ page }) => {
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    if (scenario === 'webgl-unavailable') {
      await page.addInitScript(() => {
        const original = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
          return kind.includes('webgl') ? null : original.call(this, kind, ...args);
        };
      });
    }
    await openReport(page, { block: url => scenario === 'three-blocked'
      ? /three|OrbitControls/.test(url) : scenario === 'controls-blocked' && url.includes('OrbitControls') });
    await expect(page.locator('.three-viewport [role="status"]')).toHaveCount(2);
    await expect(page.locator('.three-controls button:disabled')).toHaveCount(4);
    await expect.poll(() => page.evaluate(() => Object.keys(Chart.instances).length)).toBe(7);
    await assertTablesWork(page);
    expect(errors).toEqual([]);
  });
}

test('one failed scene leaves the other scene running', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await openReport(page, { appendScript: url => url.includes('three.min.js') ? `
    const OriginalRenderer = THREE.WebGLRenderer;
    let attempts = 0;
    THREE.WebGLRenderer = function (...args) {
      if (++attempts === 1) throw new Error('Injected first scene failure');
      return new OriginalRenderer(...args);
    };` : '' });
  await expect(page.locator('#viewport-velocity [role="status"]')).toBeVisible();
  await expect.poll(() => page.evaluate(() => cadRenderer.info.render.calls > 0)).toBe(true);
  await expect.poll(() => page.evaluate(() => Object.keys(Chart.instances).length)).toBe(7);
  expect(errors).toEqual([]);
});

test('one failed chart leaves the other charts running', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await openReport(page, { appendScript: url => url.includes('chart.umd') ? `
    window.Chart = new Proxy(Chart, { construct(target, args) {
      if (args[0].id === 'chart-weekly-combo') throw new Error('Injected chart failure');
      return Reflect.construct(target, args);
    }});` : '' });
  await expect(page.locator('.chart-canvas-wrap [role="status"]')).toHaveCount(1);
  await expect.poll(() => page.evaluate(() => Object.keys(Chart.instances).length)).toBe(6);
  await assertTablesWork(page);
  expect(errors).toEqual([]);
});

test('blocked Chart.js leaves both 3D scenes and tables running', async ({ page }) => {
  await openReport(page, { block: url => url.includes('chart.umd') });
  await expect(page.locator('.chart-canvas-wrap [role="status"]')).toHaveCount(7);
  await expect.poll(() => page.evaluate(() => [velRenderer.info.render.calls, cadRenderer.info.render.calls]
    .every(n => n > 0))).toBe(true);
  await assertTablesWork(page);
});

test('a local report remains readable and filterable with networking disabled', async ({ page, context }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await context.setOffline(true);
  await page.goto(pathToFileURL(path.join(root, 'test-results/report.html')).href);
  await expect(page.locator('.visualization-fallback')).toHaveCount(9);
  await expect(page.locator('canvas')).toHaveCount(0);
  await assertTablesWork(page);
  expect(errors).toEqual([]);
});

