'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { ReadBridge, dockerArguments } = require('./bridge.cjs');
const { plainRecord, validateStoreId, validateConnection } = require('./security.cjs');

const UUID7 = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const HASH = /^[0-9a-f]{64}$/;
const FIELDS = {
  catalog: [], history: ['realm_id'],
  create: ['name', 'description', 'actor', 'reason', 'request_id'],
  revise: ['realm_id', 'expected_revision_id', 'name', 'description', 'members', 'actor', 'reason', 'request_id'],
};
function fail(code = 'invalid_realm_request') { throw new Error(code); }
function validateRealmRequest(value) {
  if (!plainRecord(value) || !Object.hasOwn(value, 'operation') || typeof value.operation !== 'string' || !Object.hasOwn(FIELDS, value.operation)) fail();
  const fields = FIELDS[value.operation];
  if (Object.keys(value).length !== fields.length + 1 || fields.some(field => !Object.hasOwn(value, field))) fail();
  const result = { operation: value.operation };
  for (const field of fields) {
    const item = value[field];
    if (field === 'members') {
      if (!Array.isArray(item)) fail();
      const seen = new Set();
      result.members = item.map(member => {
        if (!plainRecord(member) || Object.keys(member).length !== 3
            || !['store_id', 'member_kind', 'member_id'].every(key => Object.hasOwn(member, key))) fail();
        validateStoreId(member.store_id);
        if (!['data', 'data_series'].includes(member.member_kind) || typeof member.member_id !== 'string'
            || !(member.member_kind === 'data' ? HASH : UUID7).test(member.member_id)) fail();
        const key = JSON.stringify([member.store_id, member.member_kind, member.member_id]);
        if (seen.has(key)) fail('duplicate_realm_member');
        seen.add(key);
        return { store_id: member.store_id, member_kind: member.member_kind, member_id: member.member_id };
      });
    } else if (['realm_id', 'expected_revision_id', 'request_id'].includes(field)) {
      if (typeof item !== 'string' || !UUID7.test(item)) fail();
      result[field] = item;
    } else {
      if (typeof item !== 'string' || item.includes('\0') || !item.isWellFormed()
          || (field !== 'description' && !item.trim())) fail();
      result[field] = item;
    }
  }
  if (Buffer.byteLength(JSON.stringify({ request_id: 'transport-correlation', payload: result }), 'utf8') > 65000) fail('realm_request_too_large');
  return result;
}

function loadRealmConnection(workspace, packagedRoot = __dirname, selectedFile) {
  const file = selectedFile || [path.join(workspace, '.local', 'electron-ui', 'realm.json'),
    path.join(packagedRoot, 'realm.example.json')].find(value => fs.existsSync(value));
  if (!file) fail('desktop_realm_not_configured');
  const config = validateConnection(workspace, JSON.parse(fs.readFileSync(file, 'utf8')));
  if (config.wikiId !== null || config.queryDirectory !== null || Object.hasOwn(config, 'include_data_ids')) fail('invalid_realm_connection');
  return config;
}
function realmArguments(config) {
  if (config.wikiId !== null || config.queryDirectory !== null || Object.hasOwn(config, 'include_data_ids')) fail('invalid_realm_connection');
  const args = dockerArguments(config);
  args[args.indexOf('tools/desktop_bridge.py')] = 'tools/realm_bridge.py';
  return args;
}
function realmEnvelope(request_id, payload) { return { request_id, payload }; }

class RealmBridge {
  constructor(config, registry, { readerFactory = connection => new ReadBridge(connection,
    { buildArguments: realmArguments, encodeRequest: realmEnvelope }) } = {}) {
    this.registry = registry;
    this.reader = readerFactory(config);
  }
  async request(payload) {
    const request = validateRealmRequest(payload);
    if (request.operation === 'revise' && request.members.length) {
      if (!this.registry) fail('desktop_not_configured');
      const stores = [...new Set(request.members.map(member => member.store_id))];
      // Validate all store identities before starting any read, then verify
      // membership from real read-only source catalogs. Never accept a renderer
      // assertion that a Data/series exists or that a different DB owns it.
      for (const store of stores) this.registry.entry(store, false);
      const checked = await Promise.allSettled(stores.map(async store => {
        const catalog = await this.registry.request({ store_id: store, operation: 'source_catalog' });
        if (catalog?.schema_version !== 'source-catalog-v1' || catalog.read_only !== true || !Array.isArray(catalog.data)
            || catalog.data.some(data => !plainRecord(data) || typeof data.data_id !== 'string' || !HASH.test(data.data_id))) fail('realm_member_unverified');
        for (const member of request.members.filter(value => value.store_id === store)) {
          const exists = member.member_kind === 'data'
            ? catalog.data.some(data => data.data_id === member.member_id)
            : catalog.data.some(data => Array.isArray(data.versions) && data.versions.some(version => plainRecord(version)
              && version.series_id === member.member_id && version.data_id === data.data_id));
          if (!exists) fail('realm_member_not_found');
        }
      }));
      const failure = checked.find(value => value.status === 'rejected');
      if (failure) throw failure.reason;
    }
    // Data bytes and source DBs remain untouched. Only exact Realm metadata
    // reaches its separately configured catalog, after all member reads pass.
    return this.reader.request(request);
  }
  close() { this.reader.close(); }
}

module.exports = { RealmBridge, validateRealmRequest, loadRealmConnection, realmArguments, realmEnvelope };
