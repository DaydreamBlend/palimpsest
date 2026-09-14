'use strict';
// Pure host routing/security checks. Fake readers never launch Docker or a UI.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const { createRequire } = require('node:module');
const { EventEmitter } = require('node:events');
const { ConnectionRegistry, loadStoreRegistry, LEGACY_STORE_ID } = require('../connection-registry.cjs');
const { validateRequest, validateRegistry, validateConnection } = require('../security.cjs');
const { dockerArguments } = require('../bridge.cjs');

const A = '019947e2-0000-7000-8000-000000000010';
const B = '019947e2-0000-7000-8000-000000000020';
const REF = '019947e2-0000-7000-8000-000000000030';
const HASH = 'a'.repeat(64);
function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'palimpsest-registry-'));
  fs.mkdirSync(path.join(root, 'queries'));
  t.after(() => {
    const resolved = path.resolve(root);
    assert.equal(path.dirname(resolved), path.resolve(os.tmpdir()));
    assert.ok(path.basename(resolved).startsWith('palimpsest-registry-'));
    fs.rmSync(resolved, { recursive: true, force: true });
  });
  return root;
}
function connection(database = 'store_a', wiki = false) {
  return { project: 'palimpsest-test', database, wikiId: wiki ? REF : null,
    queryDirectory: wiki ? 'queries' : null, artifactVolume: 'fixture_artifacts', image: 'palimpsest-test:0.21.0' };
}
function document() {
  return { schema_version: 'desktop-stores-v1', stores: [
    { store_id: A, label: '논문', connection: connection('papers', true) },
    { store_id: B, label: '코드', connection: connection('code') }] };
}
function fakeReader(config) {
  return { config, calls: [], closes: 0, connected: false,
    state() { return { connected: this.connected, error: null, database: config.database,
      workspace: config.workspace, image: config.image, secret: 'NOT_RENDERER_METADATA' }; },
    async request(payload) { this.calls.push(payload); this.connected = true; return { database: config.database, payload }; },
    close() { this.closes++; this.connected = false; } };
}
function router(root, value = document(), options = {}) {
  const readers = [];
  const registry = new ConnectionRegistry(root, value, { ...options,
    bridgeFactory: config => { const reader = fakeReader(config); readers.push(reader); return reader; } });
  return { registry, readers };
}

test('source operations accept exact typed addresses and paired owned-media refs only', () => {
  for (const payload of [{ operation: 'source_catalog' }, { operation: 'source_detail', data_id: HASH },
    { operation: 'source_information', data_id: HASH, source_execution_id: REF, information_id: REF },
    { operation: 'source_artifact', data_id: HASH },
    { operation: 'source_artifact', data_id: HASH, source_execution_id: REF, sha256: HASH }]) {
    assert.deepEqual(validateRequest(payload), payload);
  }
  for (const payload of [{ operation: 'source_information', information_id: REF, source_execution_id: REF },
    { operation: 'source_artifact', data_id: HASH, sha256: HASH },
    { operation: 'source_artifact', data_id: HASH, source_execution_id: REF },
    { operation: 'source_detail', data_id: HASH, database: 'other' },
    { operation: 'source_artifact', data_id: HASH, path: '../secret' },
    { operation: 'source_catalog', filter: 'all' },
    { operation: 'source_information', data_id: HASH, information_id: REF, source_execution_id: REF.toUpperCase() },
    { operation: 'source_detail', data_id: HASH.slice(1) }]) {
    assert.throws(() => validateRequest(payload), /invalid_desktop_request/);
  }
});

test('registry validation freezes trusted connections and rejects ambiguous identities or credentials', t => {
  const root = fixture(t), raw = document();
  const checked = validateRegistry(root, raw);
  assert.ok(Object.isFrozen(checked.stores));
  assert.ok(Object.isFrozen(checked.stores[0].connection));
  assert.equal(checked.stores[1].connection.queryDirectory, null);
  assert.equal(checked.stores[1].connection.wikiId, null);
  raw.stores[0].connection.database = 'changed';
  assert.equal(checked.stores[0].connection.database, 'papers');
  for (const mutate of [value => { value.stores[1].store_id = A; },
    value => { value.schema_version = 'unknown'; }, value => { value.extra = true; },
    value => { value.stores[0].store_id = A.toUpperCase(); }, value => { value.stores[0].label = '\n'; },
    value => { value.stores[0].connection.token = 'not-a-real-secret'; },
    value => { value.stores[0].connection.database = 'db;whoami'; },
    value => { value.stores[0].connection.queryDirectory = '..'; },
    value => { value.stores[0].connection.image = 'outside.example/image:latest'; }]) {
    const value = document(); mutate(value);
    assert.throws(() => validateRegistry(root, value));
  }
  assert.throws(() => validateRegistry(root, { schema_version: 'desktop-stores-v1', stores: [] }));
  assert.throws(() => validateConnection(root, { ...connection(), workspace: '/renderer/path' }), /invalid_connection/);
});

test('store descriptors expose safe status without connection paths or backend configuration', async t => {
  const { registry, readers } = router(fixture(t));
  assert.equal(readers.flatMap(reader => reader.calls).length, 0, 'Listing stores must not start readers.');
  const descriptors = registry.stores();
  assert.deepEqual(descriptors.map(value => [value.store_id, value.hasWiki, value.hasQueries]), [[A, true, true], [B, false, false]]);
  assert.ok(descriptors.every(value => value.readOnly && !value.connected && value.error === null));
  for (const value of descriptors) {
    assert.deepEqual(Object.keys(value).sort(), ['connected', 'error', 'hasQueries', 'hasWiki', 'label', 'readOnly', 'store_id', 'version']);
  }
  descriptors[0].label = 'Renderer mutation';
  assert.equal(registry.stores()[0].label, '논문');
  await registry.request({ store_id: A, operation: 'catalog' });
  assert.equal(registry.connection(A).connected, true);
  assert.equal(registry.connection(B).connected, false);
});

test('every request captures its trusted store and equal domain IDs never alias across readers', async t => {
  const { registry, readers } = router(fixture(t));
  let finish;
  readers[0].request = payload => { readers[0].calls.push(payload); return new Promise(resolve => { finish = resolve; }); };
  const original = { store_id: A, operation: 'knowledge_node', node_revision_id: REF };
  const waiting = registry.request(original);
  original.store_id = B; original.node_revision_id = A;
  const second = await registry.request({ store_id: B, operation: 'knowledge_node', node_revision_id: REF });
  finish({ node: 'first store' });
  assert.deepEqual(await waiting, { node: 'first store' });
  assert.equal(second.database, 'code');
  assert.deepEqual(readers.map(reader => reader.calls), [
    [{ operation: 'knowledge_node', node_revision_id: REF }], [{ operation: 'knowledge_node', node_revision_id: REF }]]);
  assert.ok(readers.every(reader => reader.calls.every(call => !Object.hasOwn(call, 'store_id'))));
});

test('registry refuses missing/unknown store IDs and renderer-selected commands, databases or config', t => {
  const { registry, readers } = router(fixture(t));
  for (const payload of [{ operation: 'catalog' }, { store_id: REF, operation: 'catalog' },
    { store_id: null, operation: 'catalog' }, { store_id: A.toUpperCase(), operation: 'catalog' },
    { store_id: A, operation: 'catalog', database: 'arbitrary' },
    { store_id: A, operation: 'source_catalog', image: 'palimpsest-test:other' },
    { store_id: A, operation: 'source_catalog', connection: connection('private') },
    { store_id: A, operation: 'compile' }, Object.create({ store_id: A, operation: 'catalog' })]) {
    assert.throws(() => registry.request(payload));
  }
  assert.throws(() => registry.connection(), /invalid_desktop_store/);
  assert.throws(() => registry.connection(REF), /unknown_desktop_store/);
  assert.ok(readers.every(reader => reader.calls.length === 0));
});

test('one failed catalog and a selected reconnect do not affect other stores', async t => {
  const { registry, readers } = router(fixture(t));
  readers[0].request = async () => { throw new Error('PRIVATE C:\\deployment\\file'); };
  await assert.rejects(registry.request({ store_id: A, operation: 'catalog' }), /^Error: desktop_request_failed$/);
  await registry.request({ store_id: B, operation: 'source_catalog' });
  assert.equal(registry.stores()[0].error, 'desktop_request_failed');
  assert.equal(registry.stores()[1].connected, true);
  await registry.reconnect(B);
  assert.equal(readers[0].closes, 0);
  assert.equal(readers[1].closes, 1);
  assert.deepEqual(readers[1].calls, [{ operation: 'source_catalog' }, { operation: 'source_catalog' }]);
  registry.close();
  assert.equal(readers[0].closes, 1);
  assert.equal(readers[1].closes, 2);
});

test('registry startup probes registered sources even when the configured Wiki catalog fails', async t => {
  const { registry, readers } = router(fixture(t));
  readers[0].request = async payload => {
    readers[0].calls.push(payload);
    if (payload.operation === 'catalog') throw new Error('desktop_wiki_not_configured');
    readers[0].connected = true;
    return { data: [] };
  };
  const status = await registry.reconnect(A);
  assert.equal(status.connected, true);
  assert.deepEqual(readers[0].calls, [{ operation: 'source_catalog' }]);
  await assert.rejects(registry.request({ store_id: A, operation: 'catalog' }), /desktop_wiki_not_configured/);
  await registry.reconnect(A);
  assert.equal(registry.connection(A).connected, true);
  assert.equal(registry.connection(A).error, null);
  assert.equal(readers[1].calls.length, 0);
});

test('explicit legacy configuration retains unscoped calls; registry defaults never silently select a store', async t => {
  const root = fixture(t), file = path.join(root, 'single.json');
  fs.writeFileSync(file, JSON.stringify(connection('legacy', true)));
  const selected = loadStoreRegistry(root, { connectionFile: file });
  assert.equal(selected.legacy, true);
  assert.equal(selected.registry.stores[0].store_id, LEGACY_STORE_ID);
  const { registry, readers } = router(root, selected.registry, { legacy: selected.legacy });
  assert.equal((await registry.request({ operation: 'catalog' })).database, 'legacy');
  assert.equal(registry.connection().database, 'legacy');
  await registry.reconnect();
  assert.equal(readers[0].closes, 1);
  assert.equal(readers[0].calls.at(-1).operation, 'catalog');
  assert.throws(() => registry.request({ store_id: undefined, operation: 'catalog' }), /invalid_desktop_store/);
  assert.throws(() => loadStoreRegistry(root, { storesFile: 'any', connectionFile: file }), /ambiguous_desktop_configuration/);
});

test('registry loading uses explicit path then local registry then packaged example, without file writes', t => {
  const root = fixture(t), packagedRoot = path.join(root, 'package');
  fs.mkdirSync(packagedRoot);
  const packaged = path.join(packagedRoot, 'stores.example.json');
  fs.writeFileSync(packaged, JSON.stringify(document()));
  assert.equal(loadStoreRegistry(root, { packagedRoot }).legacy, false);
  const localDir = path.join(root, '.local', 'electron-ui');
  fs.mkdirSync(localDir, { recursive: true });
  const local = path.join(localDir, 'stores.json'), customized = document();
  customized.stores[0].label = 'Local';
  fs.writeFileSync(local, JSON.stringify(customized));
  assert.equal(loadStoreRegistry(root, { packagedRoot }).registry.stores[0].label, 'Local');
  assert.equal(loadStoreRegistry(root, { storesFile: packaged, packagedRoot }).registry.stores[0].label, '논문');
  fs.writeFileSync(local, '{bad JSON');
  assert.throws(() => loadStoreRegistry(root, { packagedRoot }), SyntaxError);
  assert.throws(() => loadStoreRegistry(root, { storesFile: path.join(root, 'missing.json'), packagedRoot }));
});

test('optional source-only reader flags omit Wiki/query mounts while legacy argv stays exact', t => {
  const root = fixture(t);
  const full = validateConnection(root, connection('legacy', true));
  assert.deepEqual(dockerArguments(full), ['compose', '-f', path.join(root, 'compose.yaml'), '-p', 'palimpsest-test',
    'run', '--rm', '--no-deps', '-T', '--pull', 'never', '--volume', 'fixture_artifacts:/var/lib/palimpsest/artifacts:ro',
    '--volume', `${path.join(root, 'queries')}:/query:ro`, '--entrypoint', 'python', 'app', 'tools/desktop_bridge.py',
    '--database-name', 'legacy', '--wiki-id', REF, '--query-directory', '/query']);
  const source = dockerArguments(validateConnection(root, { ...connection('sources'), include_data_ids: [HASH] }));
  assert.ok(!source.includes('--wiki-id') && !source.includes('--query-directory'));
  assert.equal(source.filter(value => value === '--volume').length, 1);
  assert.deepEqual(source.slice(-2), ['--include-data-id', HASH]);
});

test('reader restart ignores late events from its old child and keeps the new request isolated', async t => {
  const filename = path.join(__dirname, '..', 'bridge.cjs'), requireFromBridge = createRequire(filename);
  const children = [], spawns = [];
  function spawn(command, args, options) {
    spawns.push({ command, args, options });
    const child = new EventEmitter();
    child.stdout = new EventEmitter(); child.stdout.setEncoding = () => {};
    child.stderr = new EventEmitter(); child.stdin = new EventEmitter(); child.writes = [];
    child.stdin.write = value => { child.writes.push(JSON.parse(value)); };
    child.stdin.end = () => {}; child.kill = () => {};
    children.push(child); return child;
  }
  const sandbox = { module: { exports: {} }, process: { env: {} }, setTimeout, clearTimeout,
    require: name => name === 'node:child_process' ? { spawn } : requireFromBridge(name) };
  vm.runInNewContext(fs.readFileSync(filename, 'utf8'), sandbox, { filename });
  const bridge = new sandbox.module.exports.ReadBridge(validateConnection(fixture(t), connection()));
  t.after(() => { bridge.close(); for (const child of children) child.emit('exit'); });
  const first = bridge.request({ operation: 'source_catalog' });
  children[0].stdout.emit('data', JSON.stringify({ request_id: children[0].writes[0].request_id, result: { store: 1 } }) + '\n');
  assert.equal((await first).store, 1);
  bridge.close();
  const next = bridge.request({ operation: 'source_catalog' });
  children[0].stdout.emit('data', 'not JSON\n');
  children[0].emit('error', new Error('old child'));
  children[0].stdin.emit('error', new Error('old stdin'));
  children[0].emit('exit');
  assert.equal(bridge.error, null);
  assert.equal(bridge.pending.size, 1);
  children[1].stdout.emit('data', JSON.stringify({ request_id: children[1].writes[0].request_id, result: { store: 2 } }) + '\n');
  assert.equal((await next).store, 2);
  assert.ok(spawns.every(call => call.command === 'docker' && call.options.shell === false && call.options.windowsHide === true));
});

test('preload exposes only the frozen read API and forwards selected store IDs unchanged', async () => {
  let api;
  const calls = [];
  const sandbox = { require: () => ({ contextBridge: { exposeInMainWorld(name, value) {
    assert.equal(name, 'palimpsest'); api = value;
  } }, ipcRenderer: { invoke: (...args) => { calls.push(args); return Promise.resolve([]); } } }) };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'preload.cjs'), 'utf8'), sandbox);
  assert.ok(Object.isFrozen(api));
  assert.deepEqual(Object.keys(api).sort(), ['connection', 'realms', 'reconnect', 'request', 'stores']);
  const payload = { store_id: B, operation: 'source_catalog' };
  const realm = { operation: 'catalog' };
  await api.stores(); await api.connection(B); await api.reconnect(B); await api.request(payload); await api.realms(realm);
  assert.deepEqual(calls, [['palimpsest:stores'], ['palimpsest:connection', B], ['palimpsest:reconnect', B],
    ['palimpsest:request', payload], ['palimpsest:realms', realm]]);
});
