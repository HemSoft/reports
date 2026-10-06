const fs = require('node:fs/promises');
const path = require('node:path');
const { createHash } = require('node:crypto');
const esbuild = require('esbuild');

const root = path.resolve(__dirname, '..');
const asset = path.join(root, 'assets/report-graphics.js');
const manifestPath = path.join(root, 'assets/report-graphics.json');
const readJson = async file => JSON.parse(await fs.readFile(path.join(root, file), 'utf8'));

async function main() {
  const declared = await readJson('package.json');
  const lock = await readJson('package-lock.json');
  const versions = {};
  for (const name of ['three', 'esbuild']) {
    const installed = await readJson(`node_modules/${name}/package.json`);
    const version = declared.devDependencies[name];
    if (installed.version !== version || lock.packages[`node_modules/${name}`].version !== version) {
      throw new Error(`Asset dependency metadata versions differ: ${name}`);
    }
    versions[name] = version;
  }
  const license = (await fs.readFile(path.join(root, 'node_modules/three/LICENSE'), 'utf8')).replace(/\r\n/g, '\n');
  const result = await esbuild.build({
    absWorkingDir: root, entryPoints: ['browser/report-graphics.js'], bundle: true,
    format: 'iife', platform: 'browser', target: 'es2020', minify: true,
    // Escape shader newlines in JS strings while preserving the shader bytes.
    supported: { 'template-literal': false },
    legalComments: 'inline', banner: { js: `/* Three.js ${versions.three}\n${license}\n*/` },
    write: false,
  });
  const bytes = Buffer.from(result.outputFiles[0].contents);
  const manifest = Buffer.from(JSON.stringify({
    schema: 1, versions, bytes: bytes.length,
    integrity: `sha384-${createHash('sha384').update(bytes).digest('base64')}`,
  }, null, 2) + '\n');
  if (process.argv.includes('--check')) {
    if (!bytes.equals(await fs.readFile(asset)) || !manifest.equals(await fs.readFile(manifestPath))) {
      throw new Error('Committed browser bundle or manifest differs from a fresh pinned build');
    }
    console.log('Committed browser bundle and manifest: PASS');
  } else {
    await fs.mkdir(path.dirname(asset), { recursive: true });
    await fs.writeFile(asset, bytes);
    await fs.writeFile(manifestPath, manifest);
    console.log(`Built ${bytes.length} bytes for Three.js ${versions.three}`);
  }
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
