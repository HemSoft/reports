const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
fs.rmSync('test-results/performance/results.json', { force: true });
const result = spawnSync(process.execPath, ['scripts/benchmark_browser.js', '--probe'], { stdio: 'inherit', timeout: 180_000 });
const report = JSON.parse(fs.readFileSync('test-results/performance/results.json', 'utf8'));
if (result.status !== 1 || report.error || !report.violations.some(item => item.includes('heapGrowthBytes'))) {
  throw new Error('The retained-heap probe did not fail the actual budget gate as expected');
}
fs.renameSync('test-results/performance/results.json', 'test-results/performance/probe-results.json');
console.log('Controlled retained-heap violation rejected with unchanged budgets');
