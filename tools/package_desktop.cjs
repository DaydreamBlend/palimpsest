'use strict';
// Package application assets once; reuse the installed, exact Electron engine.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');
const root = path.resolve(__dirname, '..'), desktop = path.join(root, 'desktop');
const asar = require(path.join(desktop, 'node_modules/@electron/asar/lib/asar.js'));
const manifest = JSON.parse(fs.readFileSync(path.join(desktop, 'package.json')));
const output = path.resolve(process.env.PALIMPSEST_DESKTOP_PACKAGE_OUT || path.join(root, '.local/desktop/releases', manifest.version));
assert.ok(output.startsWith(root + path.sep), 'Package output must remain inside the workspace');
fs.mkdirSync(output, { recursive: true });
assert.ok(fs.realpathSync(output).startsWith(fs.realpathSync(root) + path.sep));
const archive = path.join(output, 'app.asar');
assert.ok(!fs.existsSync(archive), 'Preserve an existing published UI version');
const engine = require(path.join(desktop, 'node_modules/electron'));
assert.ok(fs.existsSync(engine));
assert.equal(JSON.parse(fs.readFileSync(path.join(desktop, 'node_modules/electron/package.json'))).version, manifest.devDependencies.electron);
const ownFiles = ['main.cjs', 'preload.cjs', 'bridge.cjs', 'connection-registry.cjs', 'realm-bridge.cjs',
  'security.cjs', 'index.html', 'renderer.js', 'styles.css', 'pdf-view.js', 'stores.example.json', 'realm.example.json'];
const staging = fs.mkdtempSync(path.join(output, 'build-'));
const hash = value => createHash('sha256').update(value).digest('hex');
(async () => {
  try {
    for (const file of ownFiles) fs.copyFileSync(path.join(desktop, file), path.join(staging, file));
    const packagedManifest = { name: manifest.name, productName: manifest.productName, version: manifest.version, main: manifest.main };
    fs.writeFileSync(path.join(staging, 'package.json'), JSON.stringify(packagedManifest, null, 2));
    // PDF.js runs in the sandboxed browser; its optional Node canvas is unused.
    fs.cpSync(path.join(desktop, 'node_modules/pdfjs-dist'), path.join(staging, 'node_modules/pdfjs-dist'), { recursive: true });
    await asar.createPackage(staging, archive);
    const checked = ownFiles.map(file => { const packed = asar.extractFile(archive, path.normalize(file));
      assert.deepEqual(packed, fs.readFileSync(path.join(desktop, file))); return { file, sha256: hash(packed) }; });
    for (const file of ['build/pdf.mjs', 'build/pdf.worker.mjs']) assert.deepEqual(
      asar.extractFile(archive, path.normalize('node_modules/pdfjs-dist/' + file)), fs.readFileSync(path.join(desktop, 'node_modules/pdfjs-dist', file)));
    const result = { version: manifest.version, archive, archive_bytes: fs.statSync(archive).size, archive_sha256: hash(fs.readFileSync(archive)),
      electron_engine: engine, electron_version: manifest.devDependencies.electron, engine_copied: false, checked };
    fs.writeFileSync(path.join(output, 'package-inspection.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  } finally {
    // Only this newly created staging tree can be removed, never prior packages.
    const actual = fs.realpathSync(staging);
    assert.ok(actual.startsWith(fs.realpathSync(output) + path.sep) && path.basename(actual).startsWith('build-'));
    fs.rmSync(actual, { recursive: true });
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
