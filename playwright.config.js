const { defineConfig } = require('@playwright/test');
module.exports = defineConfig({
  testDir: './tests/browser',
  outputDir: './test-results/browser',
  timeout: 30_000,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    browserName: 'chromium',
    headless: true,
    viewport: { width: 1440, height: 1000 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: { args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] },
  },
});
