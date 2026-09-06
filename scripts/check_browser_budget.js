const fs = require('node:fs');

function checkReport(report, budget) {
  const failures = [];
  if (report.schema !== 1 || !['pr', 'full', 'probe'].includes(report.mode)) failures.push('Unsupported benchmark schema/mode');
  if (report.error) failures.push(report.error);
  const expected = report.mode === 'full' ? 16 : report.mode === 'probe' ? 1 : 4;
  if (report.cases?.length !== expected) failures.push('Incomplete benchmark case matrix');
  const keys = (report.cases || []).map(c => `${c.size}-${c.width}-dpr${c.dpr}`);
  const expectedKeys = report.mode === 'full'
    ? ['small', 'large'].flatMap(size => [320, 390, 1024, 1440].flatMap(width => [1, 2].map(dpr => `${size}-${width}-dpr${dpr}`)))
    : report.mode === 'probe' ? ['small-320-dpr1'] : ['small-320-dpr1', 'small-390-dpr2', 'large-1024-dpr1', 'large-1440-dpr2'];
  if (JSON.stringify([...keys].sort()) !== JSON.stringify(expectedKeys.sort())) failures.push('Unexpected or duplicate benchmark cases');
  function limit(value, cap, label) {
    if (!Number.isFinite(cap) || cap < 0 || !Number.isFinite(value) || value > cap) failures.push(`${label}: ${value} exceeds ${cap}`);
  }
  for (const scenario of report.cases || []) {
    const count = report.mode === 'full' ? 5 : report.mode === 'probe' ? 1 : 3;
    if (scenario.samples.length !== count) failures.push(`${scenario.id}: missing repeated samples`);
    for (const [index, sample] of scenario.samples.entries()) {
      const name = `${scenario.id}/${index}`;
      if (sample.frameIntervalsMs.length < 30 || sample.frameIntervalsMs.some(n => !Number.isFinite(n))) failures.push(`${name}: insufficient frame samples`);
      limit(sample.readyMs, budget.readyMs, `${name} readyMs`);
      const orderedFrames = [...sample.frameIntervalsMs].sort((a, b) => a - b);
      limit(orderedFrames[Math.ceil(orderedFrames.length * 0.95) - 1], budget.frameP95Ms, `${name} frameP95Ms`);
      if (!Number.isFinite(sample.taskMsPerSecond)) failures.push(`${name}: missing task duration`);
      const start = sample.baseline;
      if (sample.retained.length !== (report.mode === 'full' ? 5 : 3)) failures.push(`${name}: missing retained samples`);
      for (const point of [start, ...sample.retained]) {
        limit(point.heapBytes, budget.heapBytes, `${name} heapBytes`);
        limit(point.heapBytes - start.heapBytes, budget.heapGrowthBytes, `${name} heapGrowthBytes`);
        limit(point.nodes - start.nodes, budget.nodeGrowth, `${name} nodeGrowth`);
        limit(point.listeners - start.listeners, budget.listenerGrowth, `${name} listenerGrowth`);
        limit(point.documents - start.documents, 0, `${name} documentGrowth`);
        if (point.processes.some(p => p.error)) failures.push(`${name}: unavailable process memory`);
        if (!point.processes.some(p => p.type === 'browser') || !point.processes.some(p => p.type === 'renderer') || !point.processes.some(p => p.type === 'GPU')) failures.push(`${name}: missing browser/renderer/GPU process`);
        limit(point.processes.reduce((total, p) => total + p.rssBytes, 0), budget.processRssBytes, `${name} processRssBytes`);
        limit(point.processes.reduce((total, p) => total + p.rssBytes, 0) - start.processes.reduce((total, p) => total + p.rssBytes, 0), budget.processRssGrowthBytes, `${name} processRssGrowthBytes`);
        if (point.renderers.length !== 2) failures.push(`${name}: missing renderer resources`);
        for (const [renderer, value] of point.renderers.entries()) {
          if (value.pixelRatio !== scenario.dpr) failures.push(`${name}: wrong measured renderer DPR`);
          limit(value.geometries, value.sceneGeometries, `${name} uploaded geometries exceed scene allocation`);
          for (const resource of ['sceneGeometries', 'sceneMaterials', 'textures', 'programs']) {
            limit(value[resource] - start.renderers[renderer][resource], 0, `${name} renderer${renderer} ${resource} growth`);
          }
        }
      }
    }
  }
  return failures;
}

module.exports = { checkReport };
if (require.main === module) {
  const failures = checkReport(JSON.parse(fs.readFileSync(process.argv[2], 'utf8')),
    JSON.parse(fs.readFileSync('quality/browser-budget.json', 'utf8')));
  console.log(failures.length ? failures.join('\n') : 'Saved browser report: PASS');
  process.exitCode = failures.length ? 1 : 0;
}
