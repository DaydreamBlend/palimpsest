'use strict';
// Test a separate hidden instance; production sources are read-only.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const { _electron } = require(process.env.PALIMPSEST_PLAYWRIGHT_MODULE || 'playwright');
const workspace = path.resolve(__dirname, '../..');
const run = process.env.PALIMPSEST_UI_RUN || 'source-ui'; assert.match(run, /^[A-Za-z0-9_-]+$/);
const output = path.join(workspace, 'output/t23-ui-realm', run);
const edit = process.env.PALIMPSEST_UI_REALM_EDIT === '1';
const packagePath = process.env.PALIMPSEST_UI_ASAR;
async function main() {
  await fs.mkdir(output, { recursive: true });
  const app = await _electron.launch({ executablePath: require('electron'), args: [packagePath || path.join(workspace, 'desktop')], cwd: workspace, chromiumSandbox: true,
    env: { ...process.env, PALIMPSEST_WORKSPACE: workspace, PALIMPSEST_UI_TEST: '1', PALIMPSEST_DESKTOP_CONFIG: '',
      ...(edit ? { PALIMPSEST_DESKTOP_REALM_CONFIG: path.join(workspace, 'output/t23-ui-realm/realm-test-connection.json') } : {}) } });
  const result = { checks: [], screenshots: [], errors: [], source_writes: 0, model_calls: 0, realm_test_writes: 0 };
  let page;
  const check = (name, ok) => { assert.ok(ok, name); result.checks.push(name); };
  try {
    page = await app.firstWindow(); page.setDefaultTimeout(60000);
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.setBackgroundThrottling(false));
    check('separate_hidden_window', await app.evaluate(({ BrowserWindow }) => !BrowserWindow.getAllWindows()[0].isVisible()));
    page.on('pageerror', error => result.errors.push(error.message));
    await page.waitForFunction(() => document.querySelector('#content h1')?.textContent === '모든 자료');
    check('all_sources_connected', (await page.locator('#connection-label').innerText()).startsWith('3/3'));
    check('six_distinct_sources', await page.locator('.data-card').count() === 6);
    const capture = async name => {
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const bytes = await app.evaluate(async ({ BrowserWindow }) => (await BrowserWindow.getAllWindows()[0].webContents.capturePage(undefined, { stayHidden: true, stayAwake: true })).toPNG().toString('base64'));
      await fs.writeFile(path.join(output, name + '.png'), Buffer.from(bytes, 'base64')); result.screenshots.push(name + '.png');
    };
    if (edit) {
      const name = 'UI 직접 지정 ' + Date.now();
      await page.locator('#realm-manage').click(); await page.locator('#realm-name').fill(name);
      await page.locator('#realm-description').fill('Isolated UI metadata test.'); await page.locator('#realm-reason').fill('Test manual assignment without compiling.');
      await page.getByRole('button', { name: 'Realm 만들기', exact: true }).click();
      await page.waitForFunction(name => document.querySelector('#notice').textContent.includes(name), name);
      result.realm_test_writes++;
      const created = await page.evaluate(async name => (await window.palimpsest.realms({ operation: 'catalog' })).realms.find(realm => realm.name === name), name);
      await page.locator('#data-nav').click();
      const first = page.locator('.data-card').first(); await first.locator('.assign-realm-button').click();
      await page.locator('.assignment-realm').selectOption({ label: name });
      await page.locator('.assignment-reason').fill('Attach the exact selected original.');
      await page.getByRole('button', { name: '선택 Realm에 지정', exact: true }).click();
      await page.waitForFunction(() => document.querySelector('.assignment-status')?.textContent.includes('2/2'));
      result.realm_test_writes++;
      const assigned = await page.evaluate(async id => (await window.palimpsest.realms({ operation: 'catalog' })).realms.find(realm => realm.realm_id === id), created.realm_id);
      check('all_copies_saved_in_one_revision', assigned.revision_no === 2 && assigned.members.length === 2 && new Set(assigned.members.map(member => member.member_id)).size === 1);
      result.realm_id = assigned.realm_id;
      await capture('manual-realm-assignment');
      await page.locator('#close-assignment').click(); await first.locator('.assign-realm-button').click(); await page.locator('.assignment-realm').selectOption({ label: name });
      check('membership_persisted_on_reopen', await page.getByRole('button', { name: '선택 Realm에 지정', exact: true }).isDisabled());
      await page.getByRole('button', { name: '이 범위의 소속 해제', exact: true }).click();
      await page.waitForFunction(() => document.querySelector('.assignment-status')?.textContent.includes('0/2'));
      result.realm_test_writes++;
      const history = await page.evaluate(id => window.palimpsest.realms({ operation: 'history', realm_id: id }), assigned.realm_id);
      check('assignment_removal_keeps_history', history.revisions.length === 3 && history.revisions[1].members.length === 2 && history.revisions[2].members.length === 0);
    } else {
      await capture('01-library');
      await page.locator('#realm-select').selectOption({ label: 'Palimpsest 개발' });
      check('code_realm_three_sources', await page.locator('.data-card').count() === 3);
      await page.locator('#wiki-nav').click(); await page.locator('.wiki-result').first().waitFor();
      check('wiki_realm_filter', await page.locator('.wiki-result').count() === 1);
      await page.locator('#knowledge-nav').click(); await page.locator('.knowledge-result').first().waitFor();
      check('all_42_existing_code_K_integrated', await page.locator('.knowledge-result').count() === 42);
      check('realm_stays_visible_in_K', (await page.locator('#active-realm').innerText()) === 'Palimpsest 개발');
      await capture('02-code-knowledge');
      await page.locator('#realm-select').selectOption({ label: '논문 자료' });
      await page.waitForFunction(() => document.querySelectorAll('.knowledge-result').length === 43);
      check('K_switch_uses_paper_scope', await page.locator('.knowledge-result').count() === 43);
      await page.locator('#data-nav').click();
      const paper = page.locator('.data-card').filter({ hasText: 'Factors Produced' }); await paper.getByText('Wiki 읽기 →', { exact: true }).click();
      await page.locator('.article-paper .citation').first().click(); await page.locator('#information-view .source-unit-title').waitFor();
      await capture('03-paper-evidence');
      await page.locator('#pdf-tab').click(); await page.waitForFunction(() => document.querySelector('#pdf-canvas canvas') && document.querySelector('#source-status').hidden);
      check('exact_original_pdf_14_pages', (await page.locator('#pdf-total').innerText()).includes('14'));
      await page.locator('#data-nav').click(); await page.locator('#realm-select').selectOption({ label: 'Palimpsest 개발' });
      await page.locator('.data-card').filter({ hasText: '310a3f33' }).locator('.data-title').click();
      await page.locator('.compilation-status').waitFor();
      check('full_code_I2K_still_unrun', (await page.locator('.compilation-status').innerText()).includes('성공한 모델 호출 0회'));
      check('full_code_204_I', (await page.locator('.detail-tabs').innerText()).includes('204'));
      await page.locator('#data-nav').click(); await page.locator('.data-card').filter({ hasText: 'Controlled code V2' }).locator('.data-title').click();
      await page.locator('.detail-knowledge').waitFor();
      check('V2_ten_saved_K_visible', await page.locator('.detail-knowledge .knowledge-card').count() === 10);
      await page.locator('.detail-knowledge .knowledge-card').first().getByText('지식과 생성 근거 열기', { exact: true }).click();
      await page.locator('.evidence-link').first().waitFor(); await page.locator('.evidence-link').first().click();
      await page.locator('#information-view .source-unit-title').waitFor();
      check('V2_K_traces_exact_I_without_Wiki_membership', (await page.locator('#information-view').innerText()).includes('Information'));
      await capture('04-versioned-code-evidence');
      await page.locator('#data-nav').click(); await page.locator('.assign-realm-button').first().click(); await page.locator('.assignment-realm').waitFor(); await capture('05-realm-dialog');
    }
    check('no_renderer_errors', result.errors.length === 0); result.passed = true;
  } catch (error) { result.passed = false; result.error = error.message; process.exitCode = 1; if (page) result.text = await page.locator('body').innerText().catch(() => ''); }
  finally { await fs.writeFile(path.join(output, 'result.json'), JSON.stringify(result, null, 2)); await app.close(); }
  console.log(JSON.stringify({ passed: result.passed, checks: result.checks.length, error: result.error }));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
