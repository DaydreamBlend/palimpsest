import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { extractFile, listPackage } from '../node_modules/@electron/asar/lib/asar.js';

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const workspace = path.dirname(desktop);
const output = path.join(workspace, 'output/t13-code-review-ui/app');
const root = path.join(output, 'Palimpsest-win32-x64');
const archive = path.join(root, 'resources/app.asar');
const hash = raw => createHash('sha256').update(raw).digest('hex');
const entries = listPackage(archive).map(value => value.replaceAll('\\', '/'));
const required = ['main.cjs', 'bridge.cjs', 'security.cjs', 'preload.cjs',
  'index.html', 'renderer.js', 'styles.css', 'pdf-view.js',
  'node_modules/pdfjs-dist/build/pdf.mjs', 'node_modules/pdfjs-dist/build/pdf.worker.mjs'];
const inspected = required.map(file => {
  const packed = extractFile(archive, path.normalize(file));
  const source = fs.readFileSync(path.join(desktop, file));
  assert.deepEqual(packed, source, `${file} must match the source exactly`);
  return { file, sha256: hash(packed), source_matches: true };
});
const packagedManifest = JSON.parse(extractFile(archive, 'package.json').toString());
const sourceManifest = JSON.parse(fs.readFileSync(path.join(desktop, 'package.json')));
assert.equal(packagedManifest.version, '0.2.0');
// Packager intentionally removes scripts/private/devDependencies. Compare the
// retained production manifest fields and exact application file bytes.
for (const [key, value] of Object.entries(packagedManifest)) assert.deepEqual(value, sourceManifest[key]);
assert.equal(packagedManifest.devDependencies, undefined);
assert.equal(packagedManifest.scripts, undefined);
assert.equal(JSON.parse(fs.readFileSync(path.join(desktop, 'package-lock.json'))).version, '0.2.0');
assert.equal(JSON.parse(fs.readFileSync(path.join(desktop, 'package-lock.json'))).packages[''].version, '0.2.0');
assert.ok(!entries.some(file => /^\/test(?:\/|$)|^\/node_modules\/(?:electron|@electron\/packager)(?:\/|$)/.test(file)));
const files = fs.readdirSync(root, { recursive: true, withFileTypes: true }).filter(entry => entry.isFile());
const physicalBytes = files.reduce((total, entry) => total + fs.statSync(path.join(entry.parentPath, entry.name)).size, 0);
const result = { ui_version: '0.2.0', electron_version: '44.3.0', package_path: root,
  physical_files: files.length, physical_bytes: physicalBytes, physical_mib: Number((physicalBytes / 1048576).toFixed(2)),
  asar_entries: entries.length, files: inspected, executable_sha256: hash(fs.readFileSync(path.join(root, 'Palimpsest.exe'))),
  asar_sha256: hash(fs.readFileSync(archive)), old_package_preserved: fs.existsSync(path.join(workspace, 'output/t09-electron/app/Palimpsest-win32-x64/Palimpsest.exe')),
  dependency_downloads: 0, inspection_runs_electron: false };
fs.writeFileSync(path.join(output, 'package-inspection.json'), JSON.stringify(result, null, 2));
console.log(JSON.stringify(result));
