'use strict';
// A separate hidden test window: never attach to the user's open app windows.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { _electron } = require(process.env.PALIMPSEST_PLAYWRIGHT_MODULE || 'playwright');
const workspace = path.resolve(__dirname, '../..');
const run = process.env.PALIMPSEST_UI_RUN || (process.env.PALIMPSEST_ELECTRON_EXECUTABLE ? 'packaged-ui' : 'source-ui');
assert.match(run, /^[A-Za-z0-9_-]+$/);
const output = path.join(workspace, 'output/t22-unified-electron', run);
async function main() {
  await fs.mkdir(output, { recursive: true });
  const application = await _electron.launch({ executablePath: process.env.PALIMPSEST_ELECTRON_EXECUTABLE || require('electron'),
    args: process.env.PALIMPSEST_ELECTRON_EXECUTABLE ? [] : [path.join(workspace, 'desktop')], cwd: workspace, chromiumSandbox: true,
    env: { ...process.env, PALIMPSEST_WORKSPACE: workspace, PALIMPSEST_DESKTOP_CONFIG: '', PALIMPSEST_UI_TEST: '1' } });
  const result = { started_at: new Date().toISOString(), errors: [], checks: [], screenshots: [], hidden: true, model_calls: 0 };
  let page;
  const check = (name, value) => { assert.ok(value, name); result.checks.push(name); };
  try {
    page = await application.firstWindow(); page.setDefaultTimeout(60000);
    await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.setBackgroundThrottling(false));
    page.on('pageerror', error => result.errors.push(error.message));
    check('test_window_hidden', await application.evaluate(({ BrowserWindow }) => !BrowserWindow.getAllWindows()[0].isVisible()));
    await page.waitForFunction(() => document.querySelector('#content h1')?.textContent === '모든 자료');
    check('all_three_stores_connected', (await page.locator('#connection-label').innerText()).startsWith('3/3'));
    check('all_six_unique_data_visible', await page.locator('.data-card').count() === 6);
    const capture = async name => {
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const base64 = await application.evaluate(async ({ BrowserWindow }) => (await BrowserWindow.getAllWindows()[0].webContents.capturePage(undefined, { stayHidden: true, stayAwake: true })).toPNG().toString('base64'));
      await fs.writeFile(path.join(output, name + '.png'), Buffer.from(base64, 'base64')); result.screenshots.push(name + '.png');
    };
    await capture('01-all-data');
    const stores = await page.evaluate(() => window.palimpsest.stores());
    const paperStore = stores.find(store => store.label === '논문 Wiki'), codeStore = stores.find(store => store.label === 'Palimpsest 코드');
    check('no_connection_credentials_in_descriptors', stores.every(store => !('database' in store) && !('artifactVolume' in store)));
    for (const store of stores) {
      const catalog = await page.evaluate(store_id => window.palimpsest.request({ store_id, operation: 'source_catalog' }), store.store_id);
      check(`${store.label}_registered_D3_readonly`, catalog.data.length === 3 && catalog.read_only === true);
    }
    await page.locator('#realm-select').selectOption({ label: '논문 자료' });
    check('paper_realm_has_three_unique_data', await page.locator('.data-card').count() === 3);
    const paper = page.locator('.data-card').filter({ hasText: 'Factors Produced' });
    await paper.locator('.data-title').click();
    await page.locator('.source-information-link').first().waitFor({ state: 'attached' });
    await page.getByRole('button', { name: '등록된 원본 D 열기', exact: true }).click();
    await page.waitForFunction(() => document.querySelector('#pdf-canvas canvas') && document.querySelector('#source-status')?.hidden);
    check('registered_original_pdf_has_14_pages', (await page.locator('#pdf-total').innerText()).includes('14'));
    await capture('02-paper-original');
    await page.locator('#close-source').click();
    await page.getByRole('button', { name: '이 자료의 Wiki 읽기 →', exact: true }).click();
    await page.locator('.article-paper .citation').first().waitFor();
    await page.locator('.article-paper .citation').first().click();
    await page.locator('#information-view .source-unit-title').waitFor();
    check('paper_wiki_exact_I_opened', (await page.locator('#information-view').innerText()).includes('Information'));
    await capture('03-paper-wiki-evidence');
    await page.locator('#data-nav').click();
    await page.locator('#realm-select').selectOption({ label: 'Palimpsest 개발' });
    check('code_realm_has_three_snapshots', await page.locator('.data-card').count() === 3);
    await page.locator('#data-type').selectOption('code');
    check('code_type_filter_uses_source_provenance', await page.locator('.data-card').count() === 3);
    await page.locator('.data-card').filter({ hasText: 'Wiki 읽기' }).first().locator('.data-title').click();
    await page.locator('.source-information-link').first().waitFor({ state: 'attached' });
    await page.locator('details.review-item').first().locator('summary').click();
    await page.locator('.source-information-link').first().click();
    await page.locator('#information-view .source-unit-title').waitFor();
    check('code_source_information_literal', await page.locator('#information-view .information-text').count() > 0);
    check('code_source_does_not_offer_pdf', await page.locator('#pdf-tab').isHidden());
    await capture('04-code-information');
    await page.locator('#close-source').click();
    await page.locator('#knowledge-nav').click();
    await page.locator('.knowledge-result').first().waitFor();
    const counts = await page.evaluate(async ids => {
      const replies = await Promise.all(ids.map(store_id => window.palimpsest.request({ store_id, operation: 'knowledge_catalog' })));
      return replies.reduce((sum, result) => sum + result.nodes.length, 0);
    }, [paperStore.store_id, codeStore.store_id]);
    check('knowledge_catalog_contains_both_stores', await page.locator('.knowledge-result').count() === counts);
    await page.locator('#data-nav').click(); await page.locator('#realm-manage').click();
    await page.locator('.realm-picker').waitFor();
    await page.locator('.realm-picker').selectOption({ label: 'Palimpsest 개발' });
    await page.getByText('Realm Revision 2 · 변경 이력', { exact: true }).click();
    await page.getByRole('button', { name: '보존된 이력 읽기', exact: true }).click();
    await page.getByText('보존된 Realm 변경 이력', { exact: true }).waitFor();
    check('realm_revision_history_retained', (await page.locator('#content').innerText()).includes('Revision 1'));
    await capture('05-realm-history');
    check('no_renderer_errors', result.errors.length === 0);
    result.passed = true;
  } catch (error) {
    result.passed = false; result.error = error.message;
    if (page && !page.isClosed()) result.visible_text = await page.locator('body').innerText().catch(() => '');
    process.exitCode = 1;
  } finally {
    result.completed_at = new Date().toISOString(); await fs.writeFile(path.join(output, 'result.json'), JSON.stringify(result, null, 2));
    await application.close();
  }
  console.log(JSON.stringify({ passed: result.passed, checks: result.checks.length, error: result.error }));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
