const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
fs.rmSync('test-results/performance/results.json', { force: true });
const result = spawnSync(process.execPath, ['scripts/benchmark_browser.js', '--probe'], { stdio: 'inherit', timeout: 180_000 });
const report = JSON.parse(fs.readFileSync('test-results/performance/results.json', 'utf8'));
const budget = JSON.parse(fs.readFileSync('quality/browser-budget.json', 'utf8'));
const sample = report.cases?.[0]?.samples?.[0];
const measuredGrowth = sample && sample.retained.some(point => Number.isFinite(point.heapBytes - sample.baseline.heapBytes)
  && point.heapBytes - sample.baseline.heapBytes > budget.heapGrowthBytes);
if (result.status !== 1 || report.error || !measuredGrowth || !report.violations.some(item => item.includes('heapGrowthBytes'))) {
  throw new Error('The retained-heap probe did not fail the actual budget gate as expected');
}
fs.renameSync('test-results/performance/results.json', 'test-results/performance/probe-results.json');
console.log('Controlled retained-heap violation rejected with unchanged budgets');
