'use strict';
// Run explicitly against the prepared local read service; this is not part of unit tests.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { _electron } = require(process.env.PALIMPSEST_PLAYWRIGHT_MODULE || 'playwright');
const workspace = path.resolve(__dirname, '..', '..');
const directory = path.join(workspace, 'output', 't09-electron',
  process.env.PALIMPSEST_ELECTRON_EXECUTABLE ? 'security-runtime-packaged' : 'security-runtime');

async function main() {
  await fs.mkdir(directory, { recursive: true });
  const electron = await _electron.launch({
    executablePath: process.env.PALIMPSEST_ELECTRON_EXECUTABLE || require('electron'),
    args: process.env.PALIMPSEST_ELECTRON_EXECUTABLE ? [] : [path.join(workspace, 'desktop')],
    cwd: workspace, env: { ...process.env, PALIMPSEST_WORKSPACE: workspace, PALIMPSEST_UI_TEST: '1' },
    chromiumSandbox: true, timeout: 30000,
  });
  const observations = { startedAt: new Date().toISOString(), pageErrors: [] };
  try {
    const page = await electron.firstWindow();
    page.on('pageerror', error => observations.pageErrors.push(error.message));
    await page.waitForFunction(() => typeof window.palimpsest?.request === 'function', undefined, { timeout: 15000 });
    observations.url = page.url();
    assert.equal(observations.url, 'palimpsest://app/index.html');
    observations.preferences = await electron.evaluate(({ BrowserWindow }) => {
      const preferences = BrowserWindow.getAllWindows()[0].webContents.getLastWebPreferences();
      return { contextIsolation: preferences.contextIsolation, sandbox: preferences.sandbox,
        nodeIntegration: preferences.nodeIntegration, webSecurity: preferences.webSecurity };
    });
    assert.deepEqual(observations.preferences, { contextIsolation: true, sandbox: true, nodeIntegration: false, webSecurity: true });
    observations.renderer = await page.evaluate(() => ({ require: typeof window.require, process: typeof window.process,
      api: Object.keys(window.palimpsest).sort(), frozen: Object.isFrozen(window.palimpsest) }));
    assert.deepEqual(observations.renderer, { require: 'undefined', process: 'undefined',
      api: ['connection', 'reconnect', 'request'], frozen: true });
    observations.rejectedRequests = await page.evaluate(async () => {
      const requests = [{ operation: 'compile' }, { operation: 'catalog', path: '../.env' },
        { operation: 'artifact', kind: 'original', data_id: '../source.pdf' }, { operation: 'catalog', command: 'whoami' }];
      return Promise.all(requests.map(async request => {
        try { await window.palimpsest.request(request); return false; }
        catch (error) { return error.message.includes('invalid_desktop_request'); }
      }));
    });
    assert.ok(observations.rejectedRequests.every(Boolean));
    observations.staticMainStatus = await page.evaluate(async () => (await fetch('palimpsest://app/main.cjs')).status);
    assert.equal(observations.staticMainStatus, 404);
    observations.externalFetchBlocked = await page.evaluate(async () => {
      try { await fetch('https://example.invalid/palimpsest-test'); return false; } catch { return true; }
    });
    assert.equal(observations.externalFetchBlocked, true);
    observations.popupDenied = await page.evaluate(() => window.open('https://example.invalid/palimpsest-test') === null);
    assert.equal(observations.popupDenied, true);
    assert.equal(await electron.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().length), 1);
    observations.catalog = await page.evaluate(async () => {
      const value = await window.palimpsest.request({ operation: 'catalog' });
      return { keys: Object.keys(value), pageCount: value.pages?.length, wikiId: value.wiki_id };
    });
    assert.ok(observations.catalog.pageCount > 0);
    observations.connection = await page.evaluate(() => window.palimpsest.connection());
    assert.equal(observations.connection.connected, true);
    assert.equal(observations.connection.readOnly, true);
    await page.waitForFunction(() => document.querySelector('#library')?.querySelector('button'), undefined, { timeout: 30000 });
    // A hidden native window does not paint on Windows. Show without taking focus for the capture.
    await electron.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].showInactive());
    await page.screenshot({ path: path.join(directory, 'electron-window.png') });
    assert.deepEqual(observations.pageErrors, []);
    observations.passed = true;
    console.log(JSON.stringify(observations, null, 2));
  } catch (error) {
    observations.passed = false;
    observations.failure = error.message;
    throw error;
  } finally {
    await fs.writeFile(path.join(directory, 'result.json'), JSON.stringify(observations, null, 2) + '\n');
    await electron.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
