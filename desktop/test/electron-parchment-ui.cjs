'use strict';
// A new hidden process against one explicitly configured fixture store. Never
// attach to, focus, or close the user's existing Electron windows.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const { _electron } = require(process.env.PALIMPSEST_PLAYWRIGHT_MODULE || 'playwright');
const workspace = path.resolve(__dirname, '../..');
const run = process.env.PALIMPSEST_UI_RUN || 'parchment-source-ui';
assert.match(run, /^[A-Za-z0-9_-]+$/);
const output = path.join(workspace, 'output/t24-wisdom-realm', run);
const storesFile = path.resolve(process.env.PALIMPSEST_DESKTOP_STORES || path.join(workspace, 'output/t24-wisdom-realm/parchment-stores.json'));
const UUID7 = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const HASH = /^[0-9a-f]{64}$/;

async function main() {
  await fs.mkdir(output, { recursive: true });
  const result = { started_at: new Date().toISOString(), checks: [], errors: [], screenshots: [],
    requested_operations: [], model_calls_requested: 0, source_mutations_requested: 0 };
  let app, page;
  const check = (name, ok) => { assert.ok(ok, name); result.checks.push(name); };
  const capture = async name => {
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const bytes = await app.evaluate(async ({ BrowserWindow }) => (await BrowserWindow.getAllWindows()[0].webContents
      .capturePage(undefined, { stayHidden: true, stayAwake: true })).toPNG().toString('base64'));
    await fs.writeFile(path.join(output, `${name}.png`), Buffer.from(bytes, 'base64'));
    result.screenshots.push(`${name}.png`);
  };
  try {
    result.phase = 'fixture_configuration';
    const registry = JSON.parse(await fs.readFile(storesFile, 'utf8'));
    check('one_explicit_fixture_store', registry.schema_version === 'desktop-stores-v1' && registry.stores.length === 1);
    const entry = registry.stores[0];
    assert.match(entry.store_id, UUID7);
    check('fixture_database_only', entry.connection.database === 'palimpsest_wisdom_checks');
    check('fixture_has_no_legacy_wiki_or_query', entry.connection.wikiId === null && entry.connection.queryDirectory === null);
    result.store_id = entry.store_id;
    result.phase = 'hidden_launch';
    app = await _electron.launch({ executablePath: require('electron'),
      args: [process.env.PALIMPSEST_UI_ASAR || path.join(workspace, 'desktop')], cwd: workspace, chromiumSandbox: true,
      env: { ...process.env, PALIMPSEST_WORKSPACE: workspace, PALIMPSEST_UI_TEST: '1',
        PALIMPSEST_DESKTOP_CONFIG: '', PALIMPSEST_DESKTOP_STORES: storesFile } });
    page = await app.firstWindow(); page.setDefaultTimeout(60000);
    page.on('pageerror', error => result.errors.push(error.message));
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.setBackgroundThrottling(false));
    check('separate_single_hidden_window', await app.evaluate(({ BrowserWindow }) => {
      const windows = BrowserWindow.getAllWindows(); return windows.length === 1 && !windows[0].isVisible();
    }));
    await page.waitForFunction(() => document.querySelector('#content h1')?.textContent === '모든 자료');
    check('fixture_connection_ready', (await page.locator('#connection-label').innerText()).startsWith('1/1'));
    const stores = await page.evaluate(() => window.palimpsest.stores());
    check('store_descriptor_is_readonly_and_qualified', stores.length === 1 && stores[0].store_id === entry.store_id
      && stores[0].connected && stores[0].readOnly && !stores[0].hasWiki && !stores[0].hasQueries);
    check('store_descriptor_has_no_connection_credentials', !('database' in stores[0]) && !('artifactVolume' in stores[0]) && !('dsn' in stores[0]));
    const request = async (operation, args = {}) => {
      const payload = { store_id: entry.store_id, operation, ...args };
      result.requested_operations.push(payload);
      return page.evaluate(payload => window.palimpsest.request(payload), payload);
    };
    result.phase = 'canonical_parchment_catalog';
    const [sources, catalog] = await Promise.all([request('source_catalog'), request('parchment_catalog')]);
    check('source_and_P_catalogs_are_readonly', sources.read_only === true && catalog.read_only === true);
    check('canonical_P_supported_without_Wiki', catalog.schema_version === 'parchment-catalog-v1' && catalog.supported === true && catalog.parchments.length > 0);
    const requestedId = process.env.PALIMPSEST_UI_PARCHMENT_ID;
    if (requestedId) assert.match(requestedId, UUID7);
    let selected, saved;
    for (const item of catalog.parchments) {
      if (requestedId && item.parchment_id !== requestedId) continue;
      const value = await request('parchment_get', { parchment_id: item.parchment_id });
      if (value.parchment.body.sections.some(section => section.answer_or_payload.claims.some(claim =>
        claim.k_revision_ids.length && claim.limitations.length))) { selected = item; saved = value; break; }
    }
    check('fixture_P_has_K_grounded_explanation_and_limit', Boolean(selected && saved));
    const parchment = saved.parchment;
    result.parchment_id = parchment.parchment_id; result.snapshot_sha256 = parchment.snapshot_sha256;
    result.wisdom_ids = parchment.input_wisdom_ids; result.source_data_ids = saved.source_data_ids;
    assert.match(parchment.parchment_id, UUID7); assert.match(parchment.snapshot_sha256, HASH);
    check('P_get_matches_catalog_identity_and_snapshot', saved.read_only === true && parchment.schema_version === 'parchment-v1'
      && parchment.parchment_id === selected.parchment_id && parchment.snapshot_sha256 === selected.snapshot_sha256);
    assert.deepEqual(parchment.input_wisdom_ids, selected.input_wisdom_ids);
    assert.deepEqual(saved.source_data_ids, selected.source_data_ids);
    check('frozen_P_source_scope_resolves_in_same_store', saved.source_data_ids.length > 0
      && saved.source_data_ids.every(id => HASH.test(id) && sources.data.some(source => source.data_id === id)));
    check('P_is_W_composition_not_new_direct_K_or_I', parchment.provenance.operation === 'w2p'
      && parchment.direct_k_revision_ids.length === 0 && parchment.direct_information_ids.length === 0);

    await page.locator('#wiki-nav').click(); await page.locator('.wiki-result').first().waitFor();
    check('P_list_does_not_require_legacy_Wiki', await page.locator('.wiki-result').count() === catalog.parchments.length);
    await capture('01-canonical-P-library');
    const selectedIndex = catalog.parchments.findIndex(item => item.parchment_id === selected.parchment_id);
    await page.locator('.wiki-result').nth(selectedIndex).click();
    await page.waitForFunction(title => document.querySelector('#content .document-title')?.textContent === title, parchment.title);
    result.phase = 'exact_W_content_and_citations';
    check('P_opened_from_list_as_historical_W', (await page.locator('#content .eyebrow').innerText()) === 'PARCHMENT / EXACT WISDOM'
      && (await page.locator('#content .query-intro').innerText()).includes('생성 당시 Wisdom'));
    const sections = page.locator('#content .article-section');
    check('all_W_sections_rendered', await sections.count() === parchment.body.sections.length);
    assert.deepEqual(parchment.input_wisdom_ids, parchment.body.sections.map(section => section.wisdom_id));
    const kIds = new Set();
    for (const [index, section] of parchment.body.sections.entries()) {
      const rendered = sections.nth(index), citation = parchment.citations.find(value => value.section_index === index);
      assert.match(section.wisdom_id, UUID7); assert.match(section.wisdom_snapshot_sha256, HASH);
      check(`W_${index}_query_and_UUID_exact`, await rendered.locator('h2').textContent() === section.query
        && (await rendered.locator('.revision-id').first().textContent()) === `Wisdom ${section.wisdom_id}`);
      check(`W_${index}_snapshot_bound_in_P`, citation.wisdom_id === section.wisdom_id
        && citation.wisdom_snapshot_sha256 === section.wisdom_snapshot_sha256);
      const context = rendered.locator('details').filter({ has: page.locator('summary', { hasText: '당시 질문의 조건' }) }).first();
      await context.locator('summary').click();
      check(`W_${index}_context_preserved`, await context.locator('pre').textContent() === JSON.stringify(section.context_snapshot, null, 2));
      const items = rendered.locator('.article-item');
      assert.equal(await items.count(), section.answer_or_payload.claims.length);
      for (const [ordinal, claim] of section.answer_or_payload.claims.entries()) {
        const item = items.nth(ordinal), binding = citation.claims.find(value => value.claim_key === claim.claim_key);
        assert.equal(await item.getAttribute('data-claim-key'), claim.claim_key);
        assert.equal(await item.locator('.article-text').textContent(), claim.text);
        assert.deepEqual(binding.k_revision_ids, claim.k_revision_ids);
        assert.deepEqual(binding.effective_edge_refs.map(ref => ref.semantic_kedge_revision_id), claim.effective_edge_revision_ids);
        const text = await item.textContent();
        for (const value of claim.assumptions) assert.ok(text.includes(`가정: ${value}`));
        for (const value of claim.limitations) assert.ok(text.includes(`한계: ${value}`));
        for (const id of claim.k_revision_ids) { assert.match(id, UUID7); kIds.add(id); assert.ok(text.includes(`K Revision ${id}`)); }
        for (const ref of binding.effective_edge_refs) assert.ok(text.includes(`Effective Edge ${ref.semantic_kedge_revision_id}`));
        check(`W_${index}_claim_${ordinal}_text_limits_and_K_refs_preserved`, true);
      }
      for (const unresolved of section.answer_or_payload.unresolved) assert.ok((await rendered.textContent()).includes(`미해결: ${unresolved}`));
    }
    result.k_revision_ids = [...kIds];
    check('source_only_store_displays_exact_K_ID_without_fake_Wiki_link', kIds.size > 0 && await page.locator('#content .exact-link').count() === 0);
    check('P_prose_is_literal_content', await page.locator('#content article script').count() === 0);
    await page.locator('#main').evaluate(element => { element.scrollTop = 0; });
    await capture('02-preserved-W-explanation');
    const provenance = page.locator('#content details').filter({ has: page.locator('summary', { hasText: 'Parchment 구성 이력' }) }).last();
    await provenance.locator('summary').click();
    const provenanceText = await provenance.textContent();
    check('P_provenance_UUID_and_SHA_visible', provenanceText.includes(parchment.parchment_id) && provenanceText.includes(parchment.snapshot_sha256));
    check('all_W_snapshot_refs_visible', parchment.body.sections.every(section => provenanceText.includes(section.wisdom_id)
      && provenanceText.includes(section.wisdom_snapshot_sha256)));
    await provenance.scrollIntoViewIfNeeded(); await capture('03-P-and-W-provenance');
    result.phase = 'immutable_readback';
    assert.deepEqual(await request('parchment_get', { parchment_id: parchment.parchment_id }), saved);
    check('P_and_frozen_source_scope_unchanged_after_reading', true);
    check('every_explicit_read_keeps_exact_store', result.requested_operations.every(value => value.store_id === entry.store_id
      && ['source_catalog', 'parchment_catalog', 'parchment_get'].includes(value.operation)));
    check('test_window_still_hidden', await app.evaluate(({ BrowserWindow }) => !BrowserWindow.getAllWindows()[0].isVisible()));
    check('no_renderer_errors', result.errors.length === 0); result.passed = true;
  } catch (error) {
    result.passed = false; result.error = error.message; process.exitCode = 1;
    if (page && !page.isClosed()) {
      result.visible_text = (await page.locator('body').innerText().catch(() => '')).slice(0, 20000);
      await capture('failure').catch(() => {});
    }
  } finally {
    if (app) await app.close().catch(error => { result.passed = false; result.close_error = error.message; process.exitCode = 1; });
    result.completed_at = new Date().toISOString();
    await fs.writeFile(path.join(output, 'result.json'), JSON.stringify(result, null, 2));
  }
  console.log(JSON.stringify({ passed: result.passed, checks: result.checks.length, error: result.error, output }));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
