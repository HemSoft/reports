const { test } = require('node:test');
const assert = require('node:assert/strict');
const { checkReport } = require('../../scripts/check_browser_budget');
const budget = require('../../quality/browser-budget.json');

function validReport() {
  const point = { heapBytes: 1000, nodes: 10, listeners: 2, documents: 1,
    processes: ['browser', 'renderer', 'GPU'].map(type => ({ type, rssBytes: 1000 })),
    renderers: [0, 1].map(() => ({ pixelRatio: 1, geometries: 3, sceneGeometries: 4, sceneMaterials: 2, textures: 0, programs: 1 })) };
  return { schema: 1, mode: 'probe', cases: [{ id: 'small-320-dpr1', size: 'small', width: 320, dpr: 1,
    samples: [{ readyMs: 200, frameP95Ms: 17, frameIntervalsMs: [16, 17, 17, 16, 16], taskMsPerSecond: 200,
      baseline: structuredClone(point), retained: [0, 1, 2].map(() => structuredClone(point)) }] }] };
}

test('accepts bounded resources including lazy upload of existing geometry', () => {
  const report = validReport();
  report.cases[0].samples[0].retained[1].renderers[0].geometries = 4;
  assert.deepEqual(checkReport(report, budget), []);
});

test('rejects retained allocation, process RSS growth and slow raw frames', () => {
  const report = validReport();
  const sample = report.cases[0].samples[0];
  sample.retained[2].heapBytes += budget.heapGrowthBytes + 1;
  sample.retained[2].processes[0].rssBytes += budget.processRssGrowthBytes + 1;
  sample.frameIntervalsMs.fill(budget.frameP95Ms + 1);
  sample.retained[2].renderers[0].sceneGeometries++;
  const failures = checkReport(report, budget).join('\n');
  for (const name of ['heapGrowthBytes', 'processRssGrowthBytes', 'frameP95Ms', 'sceneGeometries']) assert.match(failures, new RegExp(name));
});

test('rejects missing cases, invalid measurements and unavailable process memory', () => {
  const report = validReport();
  report.mode = 'pr';
  report.cases[0].samples[0].readyMs = NaN;
  report.cases[0].samples[0].baseline.processes[0].error = 'AccessDenied';
  const failures = checkReport(report, budget).join('\n');
  for (const name of ['case matrix', 'repeated samples', 'readyMs', 'unavailable process memory']) assert.match(failures, new RegExp(name));
});
