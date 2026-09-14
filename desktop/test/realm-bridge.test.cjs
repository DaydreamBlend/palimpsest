'use strict';
// Fake local metadata/source readers only; no Docker, SQL, UI or model calls.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { RealmBridge, validateRealmRequest, loadRealmConnection, realmArguments, realmEnvelope } = require('../realm-bridge.cjs');
const { validateRequest, validateConnection } = require('../security.cjs');

const id = number => `019af000-0000-7000-8000-${number.toString(16).padStart(12, '0')}`;
const STORE = id(1), OTHER = id(2), SERIES = id(3), DATA = 'a'.repeat(64);
const member = (member_id = DATA, store_id = STORE, member_kind = 'data') => ({ store_id, member_kind, member_id });
const create = () => ({ operation: 'create', name: '개발 자료', description: '', actor: 'local-user', reason: '분류 공간 생성', request_id: id(4) });
const revise = (members = [member()]) => ({ ...create(), operation: 'revise', realm_id: id(5), expected_revision_id: id(6), members });
function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'palimpsest-realm-bridge-'));
  t.after(() => {
    const target = path.resolve(root);
    assert.equal(path.dirname(target), path.resolve(os.tmpdir()));
    assert.ok(path.basename(target).startsWith('palimpsest-realm-bridge-'));
    fs.rmSync(target, { recursive: true, force: true });
  });
  return root;
}
function config() {
  return { project: 'palimpsest-multi-checks', database: 'palimpsest_realms', wikiId: null, queryDirectory: null,
    artifactVolume: 'palimpsest-knowledge_artifacts', image: 'palimpsest-unified:0.21.0' };
}
function fakeSources() {
  return { reads: [], entry(store) { if (![STORE, OTHER].includes(store)) throw new Error('unknown_desktop_store'); },
    async request(payload) {
      this.reads.push(payload);
      return { schema_version: 'source-catalog-v1', read_only: true, data: [{ data_id: DATA,
        versions: [{ series_id: SERIES, version_id: id(7), data_id: DATA }] }] };
    } };
}
function bridge(sources = fakeSources()) {
  const writes = [], backend = { async request(value) { writes.push(value); return { revision_id: id(8), ...value }; }, close() {} };
  return { sources, writes, backend, service: new RealmBridge(config(), sources, { readerFactory: () => backend }) };
}

test('Realm operations have closed metadata-only schemas and typed member identities', () => {
  for (const request of [{ operation: 'catalog' }, { operation: 'history', realm_id: id(5) }, create(),
    revise(), revise([]), revise([member(SERIES, STORE, 'data_series')])]) {
    assert.deepEqual(validateRealmRequest(request), request);
  }
  for (const request of [null, [], { operation: ['catalog'] }, { operation: 'constructor' },
    { ...create(), members: [] }, { ...create(), dsn: 'not-allowed' }, { ...create(), database: 'other' },
    { ...create(), actor: null }, { ...create(), reason: ' ' }, { ...create(), name: '\ud800' },
    { ...create(), request_id: id(4).replace('-7000-', '-4000-') },
    { ...revise(), expected_revision_id: undefined }, { ...revise(), members_verified: true },
    revise([member(), member()]), revise([{ ...member(), path: '/private' }]),
    revise([member(DATA.slice(1))]), revise([member(SERIES, STORE, 'version')]),
    Object.create({ operation: 'catalog' })]) assert.throws(() => validateRealmRequest(request));
  assert.throws(() => validateRequest({ operation: ['source_catalog'] }), /invalid_desktop_request/);
});

test('create/catalog/history never read sources or accept implicit membership', async () => {
  const { service, writes, sources } = bridge();
  await service.request(create());
  await service.request({ operation: 'catalog' });
  await service.request({ operation: 'history', realm_id: id(5) });
  assert.equal(sources.reads.length, 0);
  assert.deepEqual(writes.map(value => value.operation), ['create', 'catalog', 'history']);
  assert.equal(writes[0].request_id, id(4));
  await assert.rejects(service.request({ ...create(), members: [member()] }), /invalid_realm_request/);
  assert.equal(writes.length, 3);
});

test('all actual store-qualified Data and series are checked before one metadata write', async () => {
  const { service, writes, sources } = bridge();
  const request = revise([member(), member(SERIES, STORE, 'data_series'), member(DATA, OTHER)]);
  await service.request(request);
  assert.deepEqual(sources.reads, [
    { store_id: STORE, operation: 'source_catalog' }, { store_id: OTHER, operation: 'source_catalog' }]);
  assert.deepEqual(writes, [request]);
  assert.ok(writes[0].members.every(value => Object.keys(value).length === 3));
});

test('unknown store, missing Data/series, foreign version ownership and reader failure prevent every write', async () => {
  for (const mode of ['unknown_store', 'missing_data', 'missing_series', 'wrong_owner', 'not_read_only', 'offline', 'malformed']) {
    const { service, sources, writes } = bridge();
    const request = revise([mode === 'unknown_store' ? member(DATA, id(99))
      : mode === 'missing_data' ? member('b'.repeat(64))
        : mode === 'missing_series' ? member(id(99), STORE, 'data_series')
          : member(SERIES, STORE, 'data_series')]);
    const read = sources.request.bind(sources);
    sources.request = async payload => {
      if (mode === 'offline') throw new Error('desktop_backend_timeout');
      const result = await read(payload);
      if (mode === 'wrong_owner') result.data[0].versions[0].data_id = 'b'.repeat(64);
      if (mode === 'not_read_only') result.read_only = false;
      if (mode === 'malformed') result.data = [null];
      return result;
    };
    await assert.rejects(service.request(request));
    assert.equal(writes.length, 0, mode);
    if (mode === 'unknown_store') assert.equal(sources.reads.length, 0);
  }
});

test('a later failed store cannot publish a partially verified membership revision', async () => {
  const { service, sources, writes } = bridge();
  const original = sources.request.bind(sources);
  sources.request = async payload => {
    if (payload.store_id === OTHER) throw new Error('desktop_backend_disconnected');
    return original(payload);
  };
  await assert.rejects(service.request(revise([member(), member(DATA, OTHER)])), /desktop_backend_disconnected/);
  assert.equal(writes.length, 0);
});

test('renderer mutation during member verification cannot retarget or alter the captured write', async () => {
  const { service, sources, writes } = bridge();
  let release;
  sources.request = payload => { sources.reads.push(payload); return new Promise(resolve => { release = resolve; }); };
  const request = revise(), expected = structuredClone(request);
  const pending = service.request(request);
  request.members[0].store_id = OTHER; request.members[0].member_id = 'b'.repeat(64); request.name = 'Changed';
  assert.equal(writes.length, 0);
  release({ schema_version: 'source-catalog-v1', read_only: true, data: [{ data_id: DATA, versions: [] }] });
  await pending;
  assert.deepEqual(writes, [expected]);
});

test('Realm transport correlation is separate from the canonical idempotency request ID', () => {
  const request = revise();
  const first = realmEnvelope('transport-one', request), second = realmEnvelope('transport-two', request);
  assert.equal(first.request_id, 'transport-one');
  assert.equal(second.request_id, 'transport-two');
  assert.equal(first.payload.request_id, id(4));
  assert.equal(second.payload.request_id, id(4));
  assert.deepEqual(JSON.parse(JSON.stringify(first)).payload, request);
  const wired = new RealmBridge(config(), null);
  assert.deepEqual(wired.reader.encodeRequest('transport-one', request), first);
  wired.close(); // No start/request: the real shared transport creates no child.
});

test('Realm connection is selected from trusted files and uses read-only artifact mounting', t => {
  const root = fixture(t), packaged = path.join(root, 'package');
  fs.mkdirSync(packaged);
  assert.throws(() => loadRealmConnection(root, packaged), /desktop_realm_not_configured/);
  fs.writeFileSync(path.join(packaged, 'realm.example.json'), JSON.stringify(config()));
  const selected = loadRealmConnection(root, packaged);
  assert.equal(selected.database, 'palimpsest_realms');
  const args = realmArguments(selected);
  assert.ok(args.includes('tools/realm_bridge.py'));
  assert.ok(!args.includes('tools/desktop_bridge.py') && !args.includes('--wiki-id') && !args.includes('--query-directory'));
  assert.ok(args.includes('palimpsest-knowledge_artifacts:/var/lib/palimpsest/artifacts:ro'));
  const local = path.join(root, '.local', 'electron-ui');
  fs.mkdirSync(local, { recursive: true });
  fs.writeFileSync(path.join(local, 'realm.json'), JSON.stringify({ ...config(), database: 'realm_fixture' }));
  assert.equal(loadRealmConnection(root, packaged).database, 'realm_fixture');
  fs.writeFileSync(path.join(local, 'realm.json'), JSON.stringify({ ...config(), wikiId: id(9) }));
  assert.throws(() => loadRealmConnection(root, packaged), /invalid_realm_connection/);
  assert.throws(() => realmArguments(validateConnection(root, { ...config(), include_data_ids: [] })), /invalid_realm_connection/);
});
