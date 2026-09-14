'use strict';
// Run explicitly after the code Wiki read backend and connection are prepared.
// Uses retained DB results only; does not dispatch providers or write canonical data.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { _electron } = require(process.env.PALIMPSEST_PLAYWRIGHT_MODULE || 'playwright');
const workspace = path.resolve(__dirname, '../..');
const run = process.env.PALIMPSEST_UI_RUN || `run-${Date.now()}`;
assert.match(run, /^[A-Za-z0-9_-]+$/);
const output = path.join(workspace, 'output/t13-code-review-ui', run);

async function main() {
  await fs.mkdir(output, { recursive: true });
  const application = await _electron.launch({ executablePath: process.env.PALIMPSEST_ELECTRON_EXECUTABLE || require('electron'),
    args: process.env.PALIMPSEST_ELECTRON_EXECUTABLE ? [] : [path.join(workspace, 'desktop')],
    cwd: workspace, chromiumSandbox: true,
    env: { ...process.env, PALIMPSEST_WORKSPACE: workspace, PALIMPSEST_UI_TEST: '1' } });
  const result = { started_at: new Date().toISOString(), errors: [], screenshots: [] };
  let page;
  try {
    page = await application.firstWindow(); page.setDefaultTimeout(60000);
    page.on('pageerror', error => result.errors.push(error.message));
    page.on('close', () => { result.window_closed = true; });
    if (process.env.PALIMPSEST_UI_HIDDEN !== '1') {
      await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].showInactive());
    }
    result.phase = 'backend_connection';
    await page.waitForFunction(() => ['로컬 저장소 연결됨', '연결 확인 필요'].includes(document.querySelector('#connection-label')?.textContent));
    if (await page.locator('#connection-label').innerText() !== '로컬 저장소 연결됨') {
      throw new Error(`Read backend connection failed: ${await page.locator('#content').innerText()}`);
    }
    const capture = async name => {
      if (process.env.PALIMPSEST_UI_HIDDEN === '1') { result.hidden_window_dom_check = true; return; }
      await page.screenshot({ path: path.join(output, `${name}.png`) }); result.screenshots.push(`${name}.png`);
    };
    const catalog = await page.evaluate(() => window.palimpsest.request({ operation: 'catalog' }));
    const codePage = catalog.pages.find(row => row.source_format === 'code');
    assert.ok(codePage, 'A code source Wiki page must be prepared');
    result.phase = 'code_wiki';
    await page.locator('#library').getByTitle(codePage.title, { exact: true }).click();
    await page.waitForFunction(title => document.querySelector('#content h1')?.textContent === title, codePage.title);
    assert.match(await page.locator('#breadcrumb').innerText(), /코드/);
    await capture('01-code-wiki');
    await page.locator('#content .citation').first().click();
    await page.locator('#information-view .code-text').first().waitFor();
    assert.equal(await page.locator('#pdf-tab').isVisible(), false);
    assert.match(await page.locator('#information-view').innerText(), /파일 줄/);
    await capture('02-native-code-source');
    await page.locator('#close-source').click();
    await page.locator('#knowledge-nav').click();
    result.phase = 'knowledge_catalog';
    await page.locator('.knowledge-result').first().waitFor();
    const knowledge = await page.evaluate(() => window.palimpsest.request({ operation: 'knowledge_catalog' }));
    const currentInferredIndex = knowledge.nodes.findLastIndex(row => row.generation_origin?.is_inferred === true && row.source_version_status === 'current');
    const inferredIndex = currentInferredIndex >= 0 ? currentInferredIndex : knowledge.nodes.findIndex(row => row.generation_origin?.is_inferred === true);
    assert.ok(inferredIndex >= 0, 'An actual retained inferred K must be available');
    const inferred = knowledge.nodes[inferredIndex];
    result.inferred_source_version_status = inferred.source_version_status;
    result.phase = 'exact_inferred_revision';
    await page.locator('.knowledge-result').nth(inferredIndex).click();
    await page.locator('.premise-link').first().waitFor();
    assert.match(await page.locator('#content').innerText(), /추론으로 생성/);
    const exact = await page.evaluate(node_revision_id => window.palimpsest.request({ operation: 'knowledge_node', node_revision_id }), inferred.knode_revision_id);
    const premise = (exact.premise_nodes || exact.node.premise_nodes)[0];
    result.inferred_revision = inferred.knode_revision_id; result.premise_revision = premise.knode_revision_id;
    await capture('03-inferred-knowledge');
    await page.locator('.premise-link').first().click();
    await page.waitForFunction(id => document.querySelector('#content .key-value')?.textContent.includes(id), premise.knode_revision_id);
    assert.match(await page.locator('#content').innerText(), new RegExp(premise.knode_revision_id));
    await page.locator('.evidence-card .evidence-link').first().click();
    await page.locator('#information-view .provenance').first().waitFor();
    // A historical K may cite the retained Markdown I rather than a later
    // native code I. Its actual evidence must keep that original execution.
    await capture('04-retained-premise-source');
    await page.locator('#close-source').click();
    await page.locator('#reviews-nav').click();
    result.phase = 'review_catalog';
    await page.locator('.review-result').first().waitFor();
    const reviews = await page.evaluate(() => window.palimpsest.request({ operation: 'review_catalog' }));
    const unresolvedIndex = reviews.executions.findIndex(row => row.state === 'needs_human');
    assert.ok(unresolvedIndex >= 0, 'An actual unresolved review must remain visible');
    const selected = reviews.executions[unresolvedIndex];
    result.phase = 'unresolved_review';
    await page.locator('.review-result').nth(unresolvedIndex).click();
    await page.locator('.review-item').first().waitFor();
    const review = await page.evaluate(execution_id => window.palimpsest.request({ operation: 'review_status', execution_id }), selected.execution_id);
    const unresolved = review.information.find(row => row.status === 'needs_review' && row.validator_review?.reason);
    assert.ok(unresolved, 'An unresolved I must retain its actual validation reason');
    assert.ok((await page.locator('#content').innerText()).includes(unresolved.validator_review.reason));
    result.review_execution = selected.execution_id; result.pending_information = review.pending_information_ids.length;
    assert.ok(result.pending_information > 0);
    await capture('05-unresolved-review');
    if (process.env.PALIMPSEST_UI_QUERY_ID) {
      result.phase = 'accepted_inference_query';
      const queryId = process.env.PALIMPSEST_UI_QUERY_ID;
      const saved = await page.evaluate(query_id => window.palimpsest.request({ operation: 'query', query_id }), queryId);
      assert.equal(saved.accepted, true); assert.equal(saved.proposal.schema_version, 'wiki-query-answer-v2');
      const claim = saved.proposal.claims.find(row => row.epistemic_basis === 'accepted_system_inference');
      assert.ok(claim, 'The saved answer must explicitly identify accepted system inference');
      const citation = claim.knowledge_evidence[0];
      if (process.env.PALIMPSEST_UI_K_REVISION) assert.equal(citation.node_revision_id, process.env.PALIMPSEST_UI_K_REVISION);
      await page.locator('#queries-nav').click();
      await page.locator('#library').getByTitle(saved.job.question, { exact: true }).click();
      await page.locator('.query-knowledge-citation').first().waitFor();
      await page.locator('.query-knowledge-citation summary').first().click();
      const answerText = await page.locator('#content').innerText();
      assert.match(answerText, /승인된 시스템 K2K 추론/);
      assert.ok(answerText.includes(citation.node_revision_id));
      for (const premise of citation.premise_revisions) assert.ok(answerText.includes(premise.node_revision_id));
      for (const text of [...citation.generation_origin.assumptions, ...citation.generation_origin.limitations]) assert.ok(answerText.includes(text));
      const inferenceClaim = page.locator('.article-paper > .article-item').nth(saved.proposal.claims.indexOf(claim));
      assert.equal(await inferenceClaim.locator('.article-text > .citations .citation').count(), 0,
        'An inference-only answer must not manufacture direct I citations');
      result.query_id = queryId; result.query_knowledge_revision = citation.node_revision_id;
      result.query_epistemic_basis = claim.epistemic_basis;
      await capture('06-accepted-inference-query');
      for (const lineage of citation.transitive_source_refs) assert.ok(answerText.includes(lineage.information_id));
      const sourceClaim = saved.proposal.claims.find(row => row.evidence.length);
      assert.ok(sourceClaim, 'This actual mixed answer contains a separate source-grounded claim');
      const retained = sourceClaim.evidence[0];
      assert.ok(retained.source_execution_id, 'The actual direct source citation must own its source execution');
      await page.locator('.article-paper > .article-item').nth(saved.proposal.claims.indexOf(sourceClaim)).locator('.citation').first().click();
      await page.locator('#information-view .provenance').first().waitFor();
      await page.locator('#information-view .provenance').last().locator('summary').click();
      const sourceText = await page.locator('#information-view').innerText();
      assert.ok(sourceText.includes(retained.information_id));
      await capture('07-query-retained-source');
    }
    assert.deepEqual(result.errors, []); result.passed = true; result.phase = 'complete';
  } catch (error) {
    result.passed = false; result.failure = error.message;
    if (page && !page.isClosed()) {
      if (process.env.PALIMPSEST_UI_HIDDEN !== '1') {
        await page.screenshot({ path: path.join(output, 'failure.png') }).catch(() => {});
      }
      await fs.writeFile(path.join(output, 'failure-dom.txt'), await page.locator('body').innerText().catch(() => ''));
    }
    throw error;
  } finally {
    await fs.writeFile(path.join(output, 'result.json'), JSON.stringify(result, null, 2));
    await application.close();
  }
  console.log(JSON.stringify(result));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
