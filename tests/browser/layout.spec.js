const { test, expect } = require('@playwright/test');
const fs = require('node:fs/promises');
const { openReport } = require('./fixture');

for (const [width, height] of [[320, 844], [390, 844], [1024, 768], [1440, 900]]) {
  test(`layout fits ${width}x${height} with local table scrolling`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await openReport(page);
    const bounds = await page.locator('header, .header-brand, .header-actions, h1, .meta-bar, .time-badge, .btn, .three-title, .three-controls, .three-btn, .tabs-nav, .tab-btn, #table-search, footer').evaluateAll(elements => elements.map(element => {
      const rect = element.getBoundingClientRect();
      return { name: element.textContent.trim(), left: rect.left, right: rect.right, width: rect.width };
    }));
    for (const bound of bounds) {
      expect(bound.left, bound.name).toBeGreaterThanOrEqual(0);
      expect(bound.right, bound.name).toBeLessThanOrEqual(width);
    }
    await page.screenshot({ path: `test-results/layout-${width}-header.png` });
    for (const button of await page.locator('header .btn, .three-btn').all()) {
      await button.focus();
      await expect(button).toBeFocused();
      await expect(button).toBeInViewport();
    }
    await page.locator('.three-header').first().scrollIntoViewIfNeeded();
    await page.screenshot({ path: `test-results/layout-${width}-scene.png` });
    for (const summary of await page.locator('.chart-data summary').all()) {
      await summary.focus();
      await page.keyboard.press('Enter');
    }
    const table = page.locator('#data-cadence .table-wrap');
    await table.focus();
    await page.keyboard.press('ArrowRight');
    await expect.poll(() => table.evaluate(element => element.scrollLeft)).toBeGreaterThan(0);
    const scroll = await table.evaluate(element => ({ client: element.clientWidth, content: element.scrollWidth }));
    expect(scroll.content).toBeGreaterThan(scroll.client);
    await page.getByRole('tab', { name: /Repositories/ }).focus();
    await page.keyboard.press('ArrowRight');
    await expect(page.getByRole('tab', { name: /Recent Pull Requests/ })).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(page.locator('#table-search')).toBeFocused();
    await expect(page.locator('#table-search')).toBeInViewport();
    await page.locator('.table-toolbar').scrollIntoViewIfNeeded();
    await page.screenshot({ path: `test-results/layout-${width}-tables.png` });
    const documentWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(documentWidth).toBe(width);
    await fs.writeFile(`test-results/layout-${width}.json`, JSON.stringify({ width, height, documentWidth, bounds, scroll }, null, 2));
  });
}
