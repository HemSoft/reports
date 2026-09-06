const { test, expect } = require('@playwright/test');
const { openReport } = require('./fixture');

for (const dependency of ['chart.umd.js', 'three.min.js', 'OrbitControls.js']) {
  test(`rejects altered ${dependency} bytes and preserves report data`, async ({ page }) => {
    const integrityErrors = [];
    page.on('console', message => {
      if (message.type() === 'error' && /integrity|digest/i.test(message.text())) integrityErrors.push(message.text());
    });
    await openReport(page, { corruptScript: url => url.includes(dependency) });
    expect(await page.evaluate(() => window.integrityProbe)).toBeUndefined();
    expect(integrityErrors.length).toBeGreaterThan(0);
    await expect(page.locator('script[src][integrity][crossorigin="anonymous"]')).toHaveCount(3);
    await expect(page.locator('.visualization-fallback')).toHaveCount(dependency === 'chart.umd.js' ? 7 : 2);
    await page.getByRole('tab', { name: /Recent Pull Requests/ }).click();
    await expect(page.locator('#pane-prs tbody tr:visible')).toHaveCount(1);
    await page.locator('#data-cadence summary').click();
    await expect(page.locator('#data-cadence td')).toHaveCount(168);
  });
}
