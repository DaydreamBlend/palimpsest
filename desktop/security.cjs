'use strict';
const path = require('node:path');
const fs = require('node:fs');
const UUID7 = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const HASH = /^[0-9a-f]{64}$/;
const APP_URL = 'palimpsest://app/index.html';
const SPEC = {
  catalog: [[], []], page: [['page_id'], ['snapshot_id']],
  information: [['information_id', 'source_execution_id'], []],
  queries: [[], []], query: [['query_id'], []],
  knowledge_catalog: [[], []], knowledge_node: [['node_revision_id'], []],
  review_catalog: [[], []], review_status: [['execution_id'], []],
  data_grounding: [['grounding_id'], []],
  artifact: [['kind', 'data_id'], ['sha256', 'source_execution_id']],
  source_catalog: [[], []], source_detail: [['data_id'], []],
  source_information: [['data_id', 'source_execution_id', 'information_id'], []],
  source_artifact: [['data_id'], ['source_execution_id', 'sha256']],
  parchment_catalog: [[], []], parchment_get: [['parchment_id'], []],
};
function plainRecord(value) {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value)
    && [Object.prototype, null].includes(Object.getPrototypeOf(value)));
}
function validateStoreId(value) {
  if (typeof value !== 'string' || !UUID7.test(value)) throw new Error('invalid_desktop_store');
  return value;
}
function validateRequest(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)
      || ![Object.prototype, null].includes(Object.getPrototypeOf(value))
      || !Object.hasOwn(value, 'operation') || typeof value.operation !== 'string' || !Object.hasOwn(SPEC, value.operation)) throw new Error('invalid_desktop_request');
  const [required, optional] = SPEC[value.operation];
  const allowed = new Set(['operation', ...required, ...optional]);
  if (Object.keys(value).some(key => !allowed.has(key)) || required.some(key => !Object.hasOwn(value, key))) throw new Error('invalid_desktop_request');
  for (const [key, item] of Object.entries(value)) {
    if (key === 'operation') continue;
    if (key === 'kind') { if (!['original', 'image'].includes(item)) throw new Error('invalid_desktop_request'); }
    else if (typeof item !== 'string' || !(key === 'data_id' || key === 'sha256' ? HASH : UUID7).test(item)) throw new Error('invalid_desktop_request');
  }
  if (value.operation === 'artifact' && value.kind === 'image' && !value.sha256) throw new Error('invalid_desktop_request');
  if (value.operation === 'source_artifact' && Object.hasOwn(value, 'source_execution_id') !== Object.hasOwn(value, 'sha256')) throw new Error('invalid_desktop_request');
  return { ...value };
}
function validSenderUrl(raw) {
  try {
    const url = new URL(raw);
    return url.protocol === 'palimpsest:' && url.hostname === 'app' && url.pathname === '/index.html' && !url.username && !url.password && !url.port && !url.search;
  } catch { return false; }
}
function staticFile(raw, root) {
  const url = new URL(raw);
  if (url.protocol !== 'palimpsest:' || url.hostname !== 'app' || url.username || url.password || url.port) throw new Error('invalid_asset');
  const name = decodeURIComponent(url.pathname).replace(/^\//, '');
  if (name.includes('\\') || name.split('/').some(part => part === '..' || part === '.' || !part)) throw new Error('invalid_asset');
  const own = new Set(['index.html', 'renderer.js', 'styles.css', 'pdf-view.js']);
  let target, base;
  if (own.has(name)) { base = root; target = path.join(root, name); }
  else if (/^vendor\/(build\/(pdf|pdf\.worker)\.mjs|standard_fonts\/[A-Za-z0-9_.-]+|cmaps\/[A-Za-z0-9_.-]+|wasm\/[A-Za-z0-9_.-]+)$/.test(name)) {
    base = path.join(root, 'node_modules', 'pdfjs-dist'); target = path.join(base, name.slice(7));
  } else throw new Error('invalid_asset');
  const resolved = fs.realpathSync(target), parent = fs.realpathSync(base);
  const relative = path.relative(parent, resolved);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative) || !fs.statSync(resolved).isFile()) throw new Error('invalid_asset');
  return resolved;
}
function workspaceFrom(start) {
  let current = path.resolve(start);
  while (true) {
    if (fs.existsSync(path.join(current, 'compose.yaml')) && fs.existsSync(path.join(current, 'src', 'palimpsest'))) return fs.realpathSync(current);
    const parent = path.dirname(current); if (parent === current) throw new Error('workspace_not_found'); current = parent;
  }
}
const CONNECTION_DEFAULTS = Object.freeze({ project: 'palimpsest-multi-checks', database: 'palimpsest_wiki_pg',
    wikiId: '01a0941f-90b3-792b-bd4b-a3e83c18eaeb', artifactVolume: 'palimpsest-knowledge_artifacts',
    queryDirectory: 'output/t07-wiki-query-ui/query-store', image: 'palimpsest-desktop:0.9.0' });
function validateConnection(workspace, value) {
  if (!plainRecord(value) || Object.keys(value).some(key => !Object.hasOwn(CONNECTION_DEFAULTS, key) && key !== 'include_data_ids')
      || Object.keys(CONNECTION_DEFAULTS).some(key => !Object.hasOwn(value, key)
        || (typeof value[key] !== 'string' && !(['wikiId', 'queryDirectory'].includes(key) && value[key] === null)))) throw new Error('invalid_connection');
  if (Object.hasOwn(value, 'include_data_ids') && (!Array.isArray(value.include_data_ids)
      || value.include_data_ids.some(id => typeof id !== 'string' || !HASH.test(id))
      || new Set(value.include_data_ids).size !== value.include_data_ids.length)) throw new Error('invalid_connection');
  if (!/^[a-z0-9][a-z0-9_-]*$/.test(value.project) || !/^[A-Za-z0-9_][A-Za-z0-9_.-]*$/.test(value.artifactVolume)
      || !/^[a-zA-Z0-9_][a-zA-Z0-9_-]{0,62}$/.test(value.database) || (value.wikiId !== null && !UUID7.test(value.wikiId))
      || !/^palimpsest-[a-z0-9_-]+:[a-zA-Z0-9_.-]+$/.test(value.image)) throw new Error('invalid_connection');
  let query = null;
  if (value.queryDirectory !== null) {
    query = fs.realpathSync(path.resolve(workspace, value.queryDirectory));
    const relative = path.relative(workspace, query);
    if (!relative || relative.startsWith('..') || path.isAbsolute(relative) || !fs.statSync(query).isDirectory()) throw new Error('invalid_query_directory');
  }
  return Object.freeze({ ...value, workspace, queryDirectory: query,
    ...(Object.hasOwn(value, 'include_data_ids') ? { include_data_ids: Object.freeze([...value.include_data_ids]) } : {}) });
}
function loadConnection(workspace, configFile) {
  const value = configFile && fs.existsSync(configFile) ? JSON.parse(fs.readFileSync(configFile, 'utf8')) : CONNECTION_DEFAULTS;
  return validateConnection(workspace, value);
}
function validateRegistry(workspace, value) {
  if (!plainRecord(value) || Object.keys(value).some(key => !['schema_version', 'stores'].includes(key))
      || value.schema_version !== 'desktop-stores-v1' || !Array.isArray(value.stores) || !value.stores.length) throw new Error('invalid_desktop_registry');
  const identifiers = new Set();
  const stores = value.stores.map(store => {
    if (!plainRecord(store) || Object.keys(store).length !== 3
        || !['store_id', 'label', 'connection'].every(key => Object.hasOwn(store, key))) throw new Error('invalid_desktop_registry');
    validateStoreId(store.store_id);
    if (identifiers.has(store.store_id)) throw new Error('duplicate_desktop_store');
    identifiers.add(store.store_id);
    if (typeof store.label !== 'string' || !store.label.trim() || store.label.length > 120
        || /[\u0000-\u001f\u007f]/.test(store.label)) throw new Error('invalid_desktop_store_label');
    return Object.freeze({ store_id: store.store_id, label: store.label,
      connection: validateConnection(workspace, store.connection) });
  });
  return Object.freeze({ schema_version: 'desktop-stores-v1', stores: Object.freeze(stores) });
}
module.exports = { APP_URL, validateRequest, validSenderUrl, staticFile, workspaceFrom, loadConnection,
  plainRecord, validateStoreId, validateConnection, validateRegistry };
