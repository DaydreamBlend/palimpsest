'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { ReadBridge } = require('./bridge.cjs');
const { loadConnection, validateRegistry, validateStoreId, validateRequest, plainRecord } = require('./security.cjs');

const LEGACY_STORE_ID = '019947e2-0000-7000-8000-000000000001';
function errorCode(error) {
  const message = typeof error?.message === 'string' ? error.message : '';
  return /^[a-z][a-z0-9_]{0,95}$/.test(message) ? message : 'desktop_request_failed';
}

function loadStoreRegistry(workspace, { storesFile, connectionFile, packagedRoot = __dirname } = {}) {
  if (storesFile && connectionFile) throw new Error('ambiguous_desktop_configuration');
  if (!connectionFile) {
    const selected = storesFile || [path.join(workspace, '.local', 'electron-ui', 'stores.json'),
      path.join(packagedRoot, 'stores.example.json')].find(file => fs.existsSync(file));
    if (selected) return { registry: JSON.parse(fs.readFileSync(selected, 'utf8')), legacy: false };
  }
  // Preserve explicit single-connection launches and old source/package setups
  // which predate any registry. No default database is selected in registry mode.
  const { workspace: _workspace, ...connection } = loadConnection(workspace,
    connectionFile || path.join(workspace, '.local', 'electron-ui', 'connection.json'));
  return { registry: { schema_version: 'desktop-stores-v1', stores: [
    { store_id: LEGACY_STORE_ID, label: '기본 저장소', connection }] }, legacy: true };
}

class ConnectionRegistry {
  constructor(workspace, registry, { legacy = false, bridgeFactory = config => new ReadBridge(config) } = {}) {
    const checked = validateRegistry(workspace, registry);
    if (legacy && checked.stores.length !== 1) throw new Error('invalid_desktop_registry');
    this.legacy = legacy;
    this.entries = new Map(checked.stores.map(store => [store.store_id,
      { ...store, bridge: bridgeFactory(store.connection), error: null }]));
  }
  entry(storeId, missing = storeId === undefined) {
    if (missing && this.legacy) return this.entries.values().next().value;
    validateStoreId(storeId);
    const entry = this.entries.get(storeId);
    if (!entry) throw new Error('unknown_desktop_store');
    return entry;
  }
  describe(entry) {
    let state;
    try { state = entry.bridge.state(); }
    catch { state = { connected: false, error: 'desktop_backend_disconnected' }; }
    return { store_id: entry.store_id, label: entry.label, connected: state.connected === true,
      error: entry.error || (state.error ? errorCode({ message: state.error }) : null),
      readOnly: true, version: require('./package.json').version,
      hasWiki: Boolean(entry.connection.wikiId),
      hasQueries: Boolean(entry.connection.wikiId && entry.connection.queryDirectory) };
  }
  stores() { return [...this.entries.values()].map(entry => this.describe(entry)); }
  connection(storeId) {
    const entry = this.entry(storeId);
    return this.legacy ? { ...entry.bridge.state(), ...this.describe(entry) } : this.describe(entry);
  }
  async send(entry, request) {
    try {
      const result = await entry.bridge.request(request);
      entry.error = null;
      return result;
    } catch (error) {
      entry.error = errorCode(error);
      throw new Error(entry.error);
    }
  }
  request(payload) {
    if (!plainRecord(payload)) throw new Error('invalid_desktop_request');
    const { store_id, ...domainPayload } = payload;
    const request = validateRequest(domainPayload);
    // Capture this entry before asynchronous work. Later UI selection changes
    // cannot redirect an in-flight request or alias equal IDs across databases.
    const entry = this.entry(store_id, !Object.hasOwn(payload, 'store_id'));
    return this.send(entry, request);
  }
  async reconnect(storeId) {
    const entry = this.entry(storeId);
    entry.bridge.close();
    await this.send(entry, { operation: this.legacy && entry.connection.wikiId ? 'catalog' : 'source_catalog' });
    return this.connection(entry.store_id);
  }
  close() { for (const entry of this.entries.values()) entry.bridge.close(); }
}

module.exports = { ConnectionRegistry, loadStoreRegistry, LEGACY_STORE_ID };
