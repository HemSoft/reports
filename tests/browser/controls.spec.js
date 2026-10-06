const { test, expect } = require('@playwright/test');
const { openReport } = require('./fixture');

test('bundled OrbitControls orbits by dragging and buttons stop and reset the scene', async ({ page }) => {
  await openReport(page);
  const canvas = page.locator('#viewport-velocity canvas');
  await canvas.scrollIntoViewIfNeeded();
  const rotation = await page.evaluate(() => velScene.rotation.y);
  await expect.poll(() => page.evaluate(() => velScene.rotation.y)).toBeGreaterThan(rotation);
  await page.getByRole('button', { name: 'Auto-rotate weekly velocity' }).click();
  const stopped = await page.evaluate(() => velScene.rotation.y);
  await page.waitForTimeout(150);
  expect(await page.evaluate(() => velScene.rotation.y)).toBe(stopped);
  const before = await page.evaluate(() => velCamera.position.toArray());
  const box = await canvas.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 100, box.y + box.height / 2 + 40, { steps: 10 });
  await page.mouse.up();
  await expect.poll(() => page.evaluate(start => velCamera.position.toArray()
    .reduce((sum, value, i) => sum + Math.abs(value - start[i]), 0), before)).toBeGreaterThan(1);
  // Let damping settle before checking that reset restores the default camera.
  await expect.poll(async () => {
    const previous = await page.evaluate(() => velCamera.position.toArray());
    await page.waitForTimeout(100);
    return page.evaluate(start => velCamera.position.toArray()
      .reduce((sum, value, i) => sum + Math.abs(value - start[i]), 0), previous);
  }).toBeLessThan(0.01);
  await page.getByRole('button', { name: 'Reset weekly velocity camera' }).click();
  await expect.poll(() => page.evaluate(() => velCamera.position.toArray()
    .reduce((sum, value, i) => sum + Math.abs(value - [28, 26, 36][i]), 0))).toBeLessThan(0.1);
  expect(await page.evaluate(() => velScene.rotation.y)).toBe(0);
});
