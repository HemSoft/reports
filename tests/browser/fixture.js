const path = require('node:path');
const fs = require('node:fs/promises');

const root = path.resolve(__dirname, '../..');
const scripts = new Map([
  ['https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.js', 'node_modules/chart.js/dist/chart.umd.js'],
  ['https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js', 'node_modules/three/build/three.min.js'],
  ['https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js', 'node_modules/three/examples/js/controls/OrbitControls.js'],
]);

async function openReport(page, { block = () => false, appendScript = () => '', corruptScript = () => false,
  reportPath = path.join(root, 'test-results/report.html') } = {}) {
  await page.route('**/*', async route => {
    const url = route.request().url();
    if (url === 'http://report.test/') {
      let body = await fs.readFile(reportPath, 'utf8');
      // Fault simulations run separately after the real dependency passes SRI.
      body = body.replace(/<script src="([^"]+)"[^>]*><\/script>/g, (tag, src) => {
        const injection = appendScript(src);
        return tag + (injection ? `<script>${injection}</script>` : '');
      });
      return route.fulfill({ body, contentType: 'text/html' });
    }
    if (block(url)) return route.abort('blockedbyclient');
    if (scripts.has(url)) {
      const body = await fs.readFile(path.join(root, scripts.get(url)), 'utf8');
      return route.fulfill({ body: body + (corruptScript(url) ? '\nwindow.integrityProbe = true;' : ''),
        contentType: 'application/javascript', headers: { 'Access-Control-Allow-Origin': '*' } });
    }
    if (url.startsWith('https://fonts.googleapis.com/')) {
      return route.fulfill({ body: '', contentType: 'text/css' });
    }
    if (url.startsWith('https://avatars.githubusercontent.com/')) {
      return route.fulfill({ body: '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>', contentType: 'image/svg+xml' });
    }
    throw new Error(`Unexpected external request: ${url}`);
  });
  await page.goto('http://report.test/');
}

module.exports = { openReport, root };
