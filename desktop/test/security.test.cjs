'use strict';
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { validateRequest, validSenderUrl, staticFile, workspaceFrom, loadConnection } = require('../security.cjs');

const ID = '01a0941f-90b3-792b-bd4b-a3e83c18eaeb';
const HASH = 'a'.repeat(64);
function fixture(t) {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'palimpsest-desktop-security-'));
  t.after(() => {
    const resolved = path.resolve(base);
    assert.equal(path.dirname(resolved), path.resolve(os.tmpdir()));
    assert.ok(path.basename(resolved).startsWith('palimpsest-desktop-security-'));
    fs.rmSync(resolved, { recursive: true, force: true });
  });
  const root = path.join(base, 'workspace');
  fs.mkdirSync(root);
  return { base, root };
}
function put(file, text = '') { fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, text); return fs.realpathSync(file); }

test('only the eleven typed read operations pass without changing their IDs', () => {
  const valid = [
    { operation: 'catalog' }, { operation: 'queries' },
    { operation: 'page', page_id: ID }, { operation: 'page', page_id: ID, snapshot_id: ID },
    { operation: 'information', information_id: ID, source_execution_id: ID },
    { operation: 'query', query_id: ID },
    { operation: 'knowledge_catalog' }, { operation: 'review_catalog' },
    { operation: 'knowledge_node', node_revision_id: ID },
    { operation: 'review_status', execution_id: ID },
    { operation: 'data_grounding', grounding_id: ID },
    { operation: 'artifact', kind: 'original', data_id: HASH },
    { operation: 'artifact', kind: 'image', data_id: HASH, sha256: HASH, source_execution_id: ID },
  ];
  for (const value of valid) { assert.deepEqual(validateRequest(value), value); assert.notEqual(validateRequest(value), value); }
});

test('IPC rejects missing fields, unknown writes, shell commands and filesystem arguments', () => {
  for (const value of [null, [], 'catalog', 1, {}, { operation: 'constructor' }, { operation: '__proto__' },
    { operation: 'compile' }, { operation: 'catalog', command: 'docker rm test' },
    { operation: 'catalog', args: ['--json'] }, { operation: 'catalog', path: '../secrets' },
    { operation: 'catalog', database: 'another_database' }, { operation: 'catalog', artifact_path: 'C:\\secret' },
    { operation: 'page' }, { operation: 'information', information_id: ID },
    { operation: 'knowledge_node' }, { operation: 'review_status' },
    { operation: 'data_grounding' }, { operation: 'data_grounding', grounding_id: ID, data_id: HASH },
    { operation: 'review_resume', execution_id: ID },
    { operation: 'knowledge_catalog', data_version_id: ID },
    { operation: 'knowledge_node', node_revision_id: ID, current: true },
    { operation: 'artifact', kind: 'image', data_id: HASH },
    { operation: 'artifact', kind: 'pdf', data_id: HASH },
    { operation: 'artifact', kind: 'original', data_id: HASH, sha256: null },
    JSON.parse('{"operation":"catalog","__proto__":{"operation":"compile"}}')]) {
    assert.throws(() => validateRequest(value), /invalid_desktop_request/, JSON.stringify(value));
  }
});

test('IPC rejects inherited operations and non-record objects', () => {
  for (const value of [Object.create({ operation: 'catalog' }), Object.assign(new Date(), { operation: 'catalog' }),
    Object.assign(Object.create({ shell: 'command' }), { operation: 'catalog' })]) {
    assert.throws(() => validateRequest(value), /invalid_desktop_request/);
  }
});

test('IDs require canonical lowercase UUIDv7 and full SHA-256 strings', () => {
  for (const id of [ID.toUpperCase(), ID.replace('-792b-', '-492b-'), ID.replace('-bd4b-', '-7d4b-'),
    ` ${ID}`, `${ID}\n`, `${ID};whoami`, '', null, 1, [ID], { id: ID }]) {
    assert.throws(() => validateRequest({ operation: 'page', page_id: id }), /invalid_desktop_request/);
    assert.throws(() => validateRequest({ operation: 'knowledge_node', node_revision_id: id }), /invalid_desktop_request/);
    assert.throws(() => validateRequest({ operation: 'review_status', execution_id: id }), /invalid_desktop_request/);
    assert.throws(() => validateRequest({ operation: 'data_grounding', grounding_id: id }), /invalid_desktop_request/);
  }
  for (const hash of [HASH.toUpperCase(), HASH.slice(1), `${HASH}0`, `${HASH}\n`, '../original.pdf', null, [HASH]]) {
    assert.throws(() => validateRequest({ operation: 'artifact', kind: 'original', data_id: hash }), /invalid_desktop_request/);
  }
});

test('sender validation accepts only the app document, with an optional fragment', () => {
  assert.equal(validSenderUrl('palimpsest://app/index.html'), true);
  assert.equal(validSenderUrl('palimpsest://app/index.html#source'), true);
  for (const url of ['https://app/index.html', 'file:///index.html', 'palimpsest://app.evil/index.html',
    'palimpsest://evil@app/index.html', 'palimpsest://app:4000/index.html', 'palimpsest://app/renderer.js',
    'palimpsest://app/index.html?operation=compile', 'palimpsest://app/index.html/extra',
    'palimpsest://app/%69ndex.html', 'about:blank', 'not a URL']) assert.equal(validSenderUrl(url), false, url);
});

test('static protocol serves only owned UI and PDF.js vendor files', t => {
  const { root } = fixture(t);
  for (const name of ['index.html', 'renderer.js', 'styles.css', 'pdf-view.js']) {
    const file = put(path.join(root, name), 'test');
    assert.equal(staticFile(`palimpsest://app/${name}`, root), file);
  }
  for (const name of ['build/pdf.mjs', 'build/pdf.worker.mjs', 'cmaps/Adobe-CNS1-UCS2.bcmap',
    'standard_fonts/FoxitSans.pfb', 'wasm/openjpeg.wasm']) {
    const file = put(path.join(root, 'node_modules', 'pdfjs-dist', name), 'test');
    assert.equal(staticFile(`palimpsest://app/vendor/${name}`, root), file);
  }
  put(path.join(root, 'main.cjs'), 'private');
  put(path.join(root, '.env'), 'private');
  for (const url of ['palimpsest://app/main.cjs', 'palimpsest://app/.env', 'palimpsest://app/node_modules/electron/index.js',
    'palimpsest://app/vendor/package.json', 'palimpsest://app/vendor/build/../../main.cjs',
    'palimpsest://app/vendor/build/%2e%2e%2f%2e%2e%2f.env', 'palimpsest://app/%5c..%5c.env',
    'palimpsest://app/vendor/build/pdf.mjs%00', 'palimpsest://app/%', 'https://app/index.html',
    'palimpsest://evil/index.html', 'palimpsest://user@app/index.html', 'palimpsest://app:123/index.html']) {
    assert.throws(() => staticFile(url, root), undefined, url);
  }
});

test('static protocol follows real paths and rejects vendor junction escapes', t => {
  const { base, root } = fixture(t);
  const external = path.join(base, 'outside');
  put(path.join(external, 'openjpeg.wasm'), 'outside');
  const vendor = path.join(root, 'node_modules', 'pdfjs-dist');
  fs.mkdirSync(vendor, { recursive: true });
  fs.symlinkSync(external, path.join(vendor, 'wasm'), process.platform === 'win32' ? 'junction' : 'dir');
  assert.throws(() => staticFile('palimpsest://app/vendor/wasm/openjpeg.wasm', root), /invalid_asset/);
});

test('workspace discovery walks parents only and does not invent a workspace', t => {
  const { base, root } = fixture(t);
  put(path.join(root, 'compose.yaml'));
  fs.mkdirSync(path.join(root, 'src', 'palimpsest'), { recursive: true });
  fs.mkdirSync(path.join(root, 'desktop', 'nested'), { recursive: true });
  assert.equal(workspaceFrom(path.join(root, 'desktop', 'nested')), fs.realpathSync(root));
  assert.throws(() => workspaceFrom(base), /workspace_not_found/);
});

test('connection configuration rejects credentials, shell syntax, remote images and path escapes', t => {
  const { base, root } = fixture(t);
  fs.mkdirSync(path.join(root, 'output', 'queries'), { recursive: true });
  const valid = { project: 'palimpsest-test', database: 'isolated_wiki', wikiId: ID,
    artifactVolume: 'test_artifacts', queryDirectory: 'output/queries', image: 'palimpsest-desktop:0.9.0' };
  const file = path.join(root, 'connection.json');
  put(file, JSON.stringify(valid));
  assert.deepEqual(loadConnection(root, file), { ...valid, workspace: root, queryDirectory: fs.realpathSync(path.join(root, 'output', 'queries')) });
  put(file, JSON.stringify({ ...valid, include_data_ids: [HASH] }));
  assert.deepEqual(loadConnection(root, file).include_data_ids, [HASH]);
  for (const selected of [HASH, [HASH, HASH], [null], ['../original'], [HASH + ';whoami']]) {
    put(file, JSON.stringify({ ...valid, include_data_ids: selected }));
    assert.throws(() => loadConnection(root, file), /invalid_connection/);
  }
  for (const value of [null, [], { ...valid, token: 'fake-not-a-secret' }, { ...valid, project: '--context other' },
    { ...valid, database: 'db; drop' }, { ...valid, artifactVolume: '../private' },
    { ...valid, image: 'external.example/app:latest' }, { ...valid, image: 'palimpsest-test:0.9 --entrypoint sh' },
    { ...valid, wikiId: ID.replace('-792b-', '-492b-') }, { ...valid, project: null }]) {
    put(file, JSON.stringify(value));
    assert.throws(() => loadConnection(root, file), /invalid_connection/);
  }
  for (const directory of ['..', '.', base]) {
    put(file, JSON.stringify({ ...valid, queryDirectory: directory }));
    assert.throws(() => loadConnection(root, file), /invalid_query_directory/);
  }
  const external = path.join(base, 'outside');
  fs.mkdirSync(external);
  fs.symlinkSync(external, path.join(root, 'linked'), process.platform === 'win32' ? 'junction' : 'dir');
  put(file, JSON.stringify({ ...valid, queryDirectory: 'linked' }));
  assert.throws(() => loadConnection(root, file), /invalid_query_directory/);
});
