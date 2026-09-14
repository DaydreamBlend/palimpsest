'use strict';
const { app, BrowserWindow, ipcMain, protocol, session, Menu } = require('electron');
const fs = require('node:fs/promises');
const path = require('node:path');
const { APP_URL, validSenderUrl, staticFile, workspaceFrom } = require('./security.cjs');
const { ConnectionRegistry, loadStoreRegistry } = require('./connection-registry.cjs');
const { RealmBridge, loadRealmConnection } = require('./realm-bridge.cjs');
const root = __dirname;
let workspace, configurationError, registry, window, realmBridge, realmConfigurationError;
try {
  workspace = workspaceFrom(process.env.PALIMPSEST_WORKSPACE || root);
  app.setPath('userData', path.join(workspace, '.local', 'electron-ui', process.env.PALIMPSEST_UI_TEST === '1' ? `test-${process.pid}` : 'profile'));
  const loaded = loadStoreRegistry(workspace, { storesFile: process.env.PALIMPSEST_DESKTOP_STORES,
    connectionFile: process.env.PALIMPSEST_DESKTOP_CONFIG, packagedRoot: root });
  registry = new ConnectionRegistry(workspace, loaded.registry, { legacy: loaded.legacy });
} catch (error) { configurationError = ['workspace_not_found', 'invalid_connection', 'invalid_query_directory',
  'ambiguous_desktop_configuration', 'invalid_desktop_registry', 'invalid_desktop_store',
  'duplicate_desktop_store', 'invalid_desktop_store_label'].includes(error.message) ? error.message : 'desktop_configuration_unreadable'; }
if (workspace) {
  try { realmBridge = new RealmBridge(loadRealmConnection(workspace, root, process.env.PALIMPSEST_DESKTOP_REALM_CONFIG), registry); }
  catch (error) { realmConfigurationError = ['desktop_realm_not_configured', 'invalid_realm_connection', 'invalid_connection']
    .includes(error.message) ? error.message : 'desktop_realm_configuration_unreadable'; }
}
app.setName('Palimpsest');
protocol.registerSchemesAsPrivileged([{ scheme: 'palimpsest', privileges: { standard: true, secure: true, supportFetchAPI: true } }]);
const CSP = "default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; font-src 'self' data: blob:; connect-src 'self'; worker-src 'self' blob:; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'";

function sender(event) {
  if (!window || event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame || !validSenderUrl(event.senderFrame.url)) throw new Error('untrusted_desktop_sender');
}
function connection(storeId) { return registry ? registry.connection(storeId) : { connected: false, error: configurationError || 'workspace_not_found', readOnly: true, version: app.getVersion() }; }
app.whenReady().then(() => {
  protocol.handle('palimpsest', async request => {
    try {
      if (request.method !== 'GET') return new Response('', { status: 405 });
      const file = staticFile(request.url, root), extension = path.extname(file);
      const type = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript', '.mjs': 'application/javascript',
        '.css': 'text/css', '.wasm': 'application/wasm', '.ttf': 'font/ttf', '.otf': 'font/otf' }[extension] || 'application/octet-stream';
      return new Response(await fs.readFile(file), { headers: { 'Content-Type': type, 'Content-Security-Policy': CSP, 'X-Content-Type-Options': 'nosniff' } });
    } catch { return new Response('Not found', { status: 404 }); }
  });
  session.defaultSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  session.defaultSession.setPermissionCheckHandler(() => false);
  session.defaultSession.webRequest.onBeforeRequest((details, callback) => {
    const allowed = details.url.startsWith('palimpsest://app/') || details.url.startsWith('blob:palimpsest://app/') || details.url.startsWith('data:');
    callback({ cancel: !allowed });
  });
  ipcMain.handle('palimpsest:stores', event => { sender(event); if (!registry) throw new Error(configurationError || 'desktop_not_configured'); return registry.stores(); });
  ipcMain.handle('palimpsest:request', async (event, payload) => { sender(event); if (!registry) throw new Error('desktop_not_configured'); return registry.request(payload); });
  ipcMain.handle('palimpsest:connection', (event, storeId) => { sender(event); return connection(storeId); });
  ipcMain.handle('palimpsest:reconnect', async (event, storeId) => { sender(event); return registry ? registry.reconnect(storeId) : connection(storeId); });
  ipcMain.handle('palimpsest:realms', async (event, payload) => { sender(event); if (!realmBridge) throw new Error(realmConfigurationError || 'desktop_realm_not_configured'); return realmBridge.request(payload); });
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { label: 'Palimpsest', submenu: [{ role: 'quit', label: '종료' }] },
    { label: '편집', submenu: [{ role: 'copy', label: '복사' }, { role: 'selectAll', label: '전체 선택' }] },
    { label: '보기', submenu: [{ role: 'reload', label: '새로 고침' }, { role: 'resetZoom', label: '기본 크기' }, { role: 'zoomIn', label: '확대' }, { role: 'zoomOut', label: '축소' }] },
  ]));
  window = new BrowserWindow({ width: 1510, height: 1000, minWidth: 1050, minHeight: 700,
    title: 'Palimpsest — 지식과 근거', backgroundColor: '#f5f4f0', show: process.env.PALIMPSEST_UI_TEST !== '1',
    webPreferences: { preload: path.join(root, 'preload.cjs'), contextIsolation: true, sandbox: true,
      nodeIntegration: false, webSecurity: true, spellcheck: false, devTools: process.env.PALIMPSEST_UI_TEST === '1' } });
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('will-navigate', event => event.preventDefault());
  window.webContents.on('will-attach-webview', event => event.preventDefault());
  window.on('closed', () => { window = null; registry?.close(); realmBridge?.close(); });
  window.loadURL(APP_URL);
});
app.on('window-all-closed', () => app.quit());
app.on('before-quit', () => { registry?.close(); realmBridge?.close(); });
