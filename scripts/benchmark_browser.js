const { chromium } = require('@playwright/test');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const { execFileSync } = require('node:child_process');
const { performance } = require('node:perf_hooks');
const { createHash } = require('node:crypto');
const { openReport, root } = require('../tests/browser/fixture');
const { checkReport } = require('./check_browser_budget');

const full = process.argv.includes('--full');
const probe = process.argv.includes('--probe');
const recordOnly = process.argv.includes('--record-only');
const output = path.join(root, 'test-results/performance');
const quantile = (values, q) => [...values].sort((a, b) => a - b)[Math.ceil(values.length * q) - 1];
const matrix = full
  ? ['small', 'large'].flatMap(size => [320, 390, 1024, 1440].flatMap(width => [1, 2].map(dpr => ({ size, width, dpr }))))
  : [{ size: 'small', width: 320, dpr: 1 }, { size: 'small', width: 390, dpr: 2 },
    { size: 'large', width: 1024, dpr: 1 }, { size: 'large', width: 1440, dpr: 2 }];
const repeats = probe ? 1 : full ? 5 : 3;
const cycles = full ? 5 : 3;

async function processes(browserSession, timed = false) {
  const { processInfo } = await browserSession.send('SystemInfo.getProcessInfo');
  const sampledAt = performance.now();
  const rows = JSON.parse(execFileSync(process.env.PYTHON || 'python',
    [path.join(root, 'scripts/process_resources.py'), JSON.stringify(processInfo)], { encoding: 'utf8' }));
  return timed ? { rows, sampledAt } : rows;
}

async function snapshot(page, session, browserSession) {
  await session.send('HeapProfiler.collectGarbage');
  const { metrics } = await session.send('Performance.getMetrics');
  const values = Object.fromEntries(metrics.map(item => [item.name, item.value]));
  const renderers = await page.evaluate(() => [velRenderer, cadRenderer].map((renderer, index) => {
    const geometries = new Set(), materials = new Set();
    [velScene, cadScene][index].traverse(object => {
      if (object.geometry) geometries.add(object.geometry);
      for (const material of Array.isArray(object.material) ? object.material : object.material ? [object.material] : []) materials.add(material);
    });
    return {
    sceneGeometries: geometries.size, sceneMaterials: materials.size,
    geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures,
    programs: renderer.info.programs.length, calls: renderer.info.render.calls,
    triangles: renderer.info.render.triangles, pixelRatio: renderer.getPixelRatio(),
    width: renderer.domElement.width, height: renderer.domElement.height,
  }; }));
  return { heapBytes: values.JSHeapUsedSize, nodes: values.Nodes, listeners: values.JSEventListeners,
    documents: values.Documents, renderers, processes: await processes(browserSession) };
}

async function workload(page, scenario) {
  await page.setViewportSize({ width: scenario.width - 1, height: scenario.height });
  await page.evaluate(() => new Promise(requestAnimationFrame));
  await page.setViewportSize({ width: scenario.width, height: scenario.height });
  await page.evaluate(() => new Promise(requestAnimationFrame));
  await page.evaluate(() => {
    const viewport = document.querySelector('#viewport-velocity');
    viewport.scrollIntoView();
    const box = viewport.getBoundingClientRect();
    viewport.dispatchEvent(new MouseEvent('mousemove', { clientX: box.x + box.width / 2, clientY: box.y + box.height / 2 }));
    const rotation = document.querySelector('[aria-label="Auto-rotate weekly velocity"]');
    rotation.click(); rotation.click();
    document.querySelector('[aria-label="Reset weekly velocity camera"]').click();
    document.querySelector('#tab-prs').click();
    const search = document.querySelector('#table-search');
    for (const value of ['no-benchmark-match', '']) {
      search.value = value;
      search.dispatchEvent(new Event('input', { bubbles: true }));
    }
    document.querySelector('#tab-repos').click();
  });
  if (probe) await page.evaluate(() => {
    window.retainedProbe ||= [];
    window.retainedProbe.push(new Array(2_000_000).fill(123));
  });
  await page.waitForTimeout(300);
}

async function sample(browser, browserSession, scenario, index) {
  const context = await browser.newContext({ viewport: { width: scenario.width, height: scenario.height }, deviceScaleFactor: scenario.dpr });
  const page = await context.newPage();
  page.setDefaultTimeout(30_000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const session = await context.newCDPSession(page);
  await session.send('Performance.enable', { timeDomain: 'timeTicks' });
  const began = performance.now();
  try {
    await openReport(page, { reportPath: path.join(output, `${scenario.size}.html`) });
    await page.waitForFunction(() => typeof Chart !== 'undefined' && Object.keys(Chart.instances).length === 7
      && velRenderer?.info.render.frame > 0 && cadRenderer?.info.render.frame > 0);
    const readyMs = performance.now() - began;
    await workload(page, scenario); // Exercise lazy interaction paths before the baseline.
    await page.waitForTimeout(1500);
    const baseline = await snapshot(page, session, browserSession);
    const before = Object.fromEntries((await session.send('Performance.getMetrics')).metrics.map(m => [m.name, m.value]));
    const processBefore = await processes(browserSession, true);
    const frames = await page.evaluate(() => new Promise((resolve, reject) => {
      const times = [];
      let first, previous;
      const deadline = setTimeout(() => reject(new Error('Frame sampling did not complete within 45 seconds')), 45_000);
      function tick(now) {
        first ??= now;
        if (previous !== undefined) times.push(now - previous);
        previous = now;
        if (now - first >= 1500 && times.length >= 30) { clearTimeout(deadline); resolve(times); }
        else requestAnimationFrame(tick);
      }
      requestAnimationFrame(tick);
    }));
    const after = Object.fromEntries((await session.send('Performance.getMetrics')).metrics.map(m => [m.name, m.value]));
    const processAfter = await processes(browserSession, true);
    const processWindowSeconds = (processAfter.sampledAt - processBefore.sampledAt) / 1000;
    const processCpu = processAfter.rows.map(item => {
      const previous = processBefore.rows.find(p => p.id === item.id);
      return { type: item.type, id: item.id, cpuSecondsPerSecond: previous ? (item.cpuTime - previous.cpuTime) / processWindowSeconds : null };
    });
    const retained = [];
    for (let cycle = 0; cycle < cycles; cycle++) {
      await workload(page, scenario);
      retained.push(await snapshot(page, session, browserSession));
    }
    if (index === 0) {
      await page.locator('#viewport-velocity').scrollIntoViewIfNeeded();
      await page.screenshot({ path: path.join(output, `${scenario.id}.png`) });
    }
    if (errors.length) throw new Error(`Browser errors: ${errors.join('; ')}`);
    return { readyMs, frameIntervalsMs: frames, frameP95Ms: quantile(frames, 0.95),
      taskMsPerSecond: (after.TaskDuration - before.TaskDuration) * 1000 / (after.Timestamp - before.Timestamp),
      processCpu, processWindowSeconds, baseline, retained };
  } finally { await context.close(); }
}

async function main() {
  const sourceHashes = {};
  for (const name of ['src/template.py', 'scripts/benchmark_browser.js', 'scripts/check_browser_budget.js',
    'scripts/generate_benchmark.py', 'scripts/process_resources.py', 'quality/browser-budget.json', 'package-lock.json']) {
    sourceHashes[name] = createHash('sha256').update(await fs.readFile(path.join(root, name))).digest('hex');
  }
  const browser = await chromium.launch({ headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const browserSession = await browser.newBrowserCDPSession();
  const gpu = (await browserSession.send('SystemInfo.getInfo')).gpu;
  const report = { schema: 1, mode: probe ? 'probe' : full ? 'full' : 'pr',
    revision: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    dirty: Boolean(execFileSync('git', ['status', '--porcelain'], { cwd: root, encoding: 'utf8' }).trim()),
    generatedAt: new Date().toISOString(), sourceHashes,
    environment: { platform: process.platform, release: os.release(), arch: os.arch(), cpus: os.cpus().length,
      cpuModel: os.cpus()[0].model, browser: browser.version(), node: process.version, gpu: gpu.devices,
      renderer: gpu.auxAttributes?.glRenderer, gpuVramBytes: null },
    methodology: { repeats, cycles, warmupMs: 1500, idleMinimumMs: 1500, minimumFrames: 30, forcedGc: true,
      workload: 'real viewport resize plus DOM mouse/input/click dispatch; no Playwright actionability waits',
      taskDuration: 'main-thread task wall time; includes blocking and is not CPU usage',
      assets: 'local pinned npm bytes; no network', renderBackend: 'SwiftShader software WebGL',
      processMemory: 'sum of per-process RSS includes shared pages; GPU-process RSS is not VRAM' },
    fixtures: JSON.parse(await fs.readFile(path.join(output, 'fixtures.json'), 'utf8')), cases: [] };
  try {
    for (const entry of probe ? matrix.slice(0, 1) : matrix) {
      const scenario = { ...entry, height: entry.width < 600 ? 844 : entry.width === 1024 ? 768 : 900,
        id: `${entry.size}-${entry.width}-dpr${entry.dpr}` };
      const samples = [];
      report.cases.push({ ...scenario, samples });
      for (let index = 0; index < repeats; index++) {
        samples.push(await sample(browser, browserSession, scenario, index));
        console.log(`${scenario.id} sample ${index + 1}/${repeats}: ready ${samples.at(-1).readyMs.toFixed(0)}ms, frame p95 ${samples.at(-1).frameP95Ms.toFixed(1)}ms`);
        await fs.writeFile(path.join(output, 'results.json'), JSON.stringify(report, null, 2));
      }
    }
  } catch (error) { report.error = error.message; }
  finally { await browser.close(); }
  const budget = JSON.parse(await fs.readFile(path.join(root, 'quality/browser-budget.json'), 'utf8'));
  report.violations = checkReport(report, budget);
  await fs.writeFile(path.join(output, 'results.json'), JSON.stringify(report, null, 2));
  console.log(report.violations.length ? report.violations.join('\n') : 'Browser performance gate: PASS');
  if (report.error || (!recordOnly && report.violations.length)) process.exitCode = 1;
}

main().catch(error => { console.error(error); process.exitCode = 1; });
