'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { _electron } = require(process.env.PALIMPSEST_PLAYWRIGHT_MODULE || 'playwright');
const workspace = path.resolve(__dirname, '..', '..');
const run = process.env.PALIMPSEST_UI_RUN || `run-${Date.now()}`;
assert.match(run, /^[A-Za-z0-9_-]+$/);
const output = path.join(workspace, 'output/t09-electron', process.env.PALIMPSEST_ELECTRON_EXECUTABLE ? 'ui-packaged' : 'ui-runtime', run);
async function main() {
  await fs.mkdir(output, { recursive: true });
  const application = await _electron.launch({
    executablePath: process.env.PALIMPSEST_ELECTRON_EXECUTABLE || require('electron'),
    args: process.env.PALIMPSEST_ELECTRON_EXECUTABLE ? [] : [path.join(workspace, 'desktop')],
    cwd: workspace, chromiumSandbox: true,
    env: { ...process.env, PALIMPSEST_WORKSPACE: workspace, PALIMPSEST_UI_TEST: '1' },
  });
  const results = { startedAt: new Date().toISOString(), errors: [], screenshots: [] };
  try {
    const page = await application.firstWindow(); page.setDefaultTimeout(45000);
    page.on('pageerror', error => results.errors.push(error.message));
    await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].showInactive());
    await page.locator('#library .page-link').first().waitFor();
    await page.waitForFunction(() => document.querySelector('#content h1')?.textContent.startsWith('Factors Produced'));
    const capture = async name => { await page.screenshot({ path: path.join(output, name + '.png') }); results.screenshots.push(name + '.png'); };
    await capture('01-library');
    const catalog = await page.evaluate(() => window.palimpsest.request({ operation: 'catalog' }));
    assert.equal(catalog.pages.length, 25); results.pages = catalog.pages.length;
    results.geometry = await page.evaluate(async () => {
      const { regionRectangle } = await import('./pdf-view.js');
      const ref = { page_size: [100, 200], bbox: [10, 20, 40, 60] };
      return { normal: regionRectangle(ref, 100, 200, 500, 1000, 0),
        rotated: regionRectangle(ref, 100, 200, 1000, 500, 90),
        mismatch: regionRectangle(ref, 400, 300, 500, 1000, 0) };
    });
    assert.deepEqual(results.geometry.normal, { left: 50, top: 100, width: 150, height: 200 });
    assert.deepEqual(results.geometry.rotated, { left: 700, top: 50, width: 200, height: 150 });
    assert.equal(results.geometry.mismatch, null);
    await page.getByRole('button', { name: /^근거 3,/ }).click();
    await page.locator('#source-panel').waitFor({ state: 'visible' });
    await page.locator('#information-view .quote-box').waitFor();
    assert.match(await page.locator('#information-view .quote-box').innerText(), /X-VIVO15/);
    await capture('02-exact-information');
    await page.locator('#pdf-tab').click();
    await page.waitForFunction(() => document.querySelector('#pdf-canvas canvas')?.dataset.pageNumber === '10', undefined, { timeout: 60000 });
    await page.waitForFunction(() => document.querySelector('#source-status')?.hidden === true, undefined, { timeout: 60000 });
    results.pdfPageCount = await page.locator('#pdf-total').innerText();
    assert.match(results.pdfPageCount, /14/);
    results.regionCount = await page.locator('#pdf-canvas .pdf-region').count(); assert.ok(results.regionCount > 0);
    await capture('03-original-pdf');
    await page.locator('#pdf-next').click();
    await page.waitForFunction(() => document.querySelector('#pdf-canvas canvas')?.dataset.pageNumber === '11');
    await page.locator('#pdf-previous').click();
    await page.waitForFunction(() => document.querySelector('#pdf-canvas canvas')?.dataset.pageNumber === '10');
    await page.locator('#pdf-rotate').click();
    await page.waitForFunction(() => { const c = document.querySelector('#pdf-canvas canvas'); return c && c.width > c.height; });
    assert.ok(await page.locator('#pdf-canvas .pdf-region').count() > 0);
    await page.locator('#pdf-zoom-in').click();
    await capture('04-pdf-rotation');
    await page.locator('#close-source').click();
    const topic = catalog.pages.find(item => item.page_id === '01a093b8-9f7d-7b31-acff-50c44a8998fe');
    assert.ok(topic);
    await page.locator('#search').fill('monocyte');
    await page.locator('#library').getByTitle(topic.title, { exact: true }).click();
    await page.waitForFunction(title => document.querySelector('#content h1')?.textContent === title, topic.title);
    results.currentContributions = await page.locator('.contribution').count();
    assert.equal(results.currentContributions, 2);
    const history = await page.locator('.history-select option').allTextContents(); assert.equal(history.length, 2);
    const older = await page.locator('.history-select option').nth(1).getAttribute('value');
    await page.locator('.history-select').selectOption(older);
    await page.waitForFunction(id => document.querySelector('.history-select')?.value === id && document.querySelector('.document-foot code')?.textContent.includes(id.slice(0, 12)), older);
    results.historicalText = await page.locator('.article-paper').innerText();
    assert.equal(await page.locator('.contribution').count(), 1);
    assert.ok(results.historicalText.includes('C1q'));
    assert.ok(!results.historicalText.includes('Intestinal host defense outcome'));
    await capture('05-topic-history');
    await page.locator('#search').fill('');
    await page.locator('#queries-nav').click();
    await page.locator('#search').fill('Clarke');
    await page.locator('#library .query-link').first().click();
    await page.locator('.query-accepted').waitFor();
    assert.match(await page.locator('#content').innerText(), /AI-41090/);
    await capture('06-verified-answer');
    await page.locator('#search').fill('통계');
    await page.locator('#library .query-link').first().click();
    await page.locator('.query-status-box').waitFor();
    assert.equal(await page.locator('.query-accepted').count(), 0);
    assert.equal(await page.locator('#content .article-paper').count(), 0);
    await capture('07-held-answer');
    await page.locator('#search').fill('BMDC');
    await page.locator('#library .query-link').first().click();
    await page.locator('.query-status-box').waitFor();
    assert.equal(await page.locator('.query-accepted').count(), 0);
    assert.equal(await page.locator('#content .article-paper').count(), 0);
    results.heldAnswersHidden = true;
    await page.locator('#reconnect').click();
    await page.waitForFunction(() => document.querySelector('#connection-label')?.textContent === '로컬 저장소 연결됨');
    results.reconnected = true;
    assert.deepEqual(results.errors, []); results.passed = true;
    delete results.historicalText;
  } catch (error) {
    results.passed = false; results.failure = error.message;
    const page = await application.firstWindow();
    await page.screenshot({ path: path.join(output, 'failure.png') }).catch(() => {});
    await fs.writeFile(path.join(output, 'failure-dom.txt'), await page.locator('body').innerText().catch(() => ''));
    throw error;
  } finally {
    await fs.writeFile(path.join(output, 'result.json'), JSON.stringify(results, null, 2));
    await application.close();
  }
  console.log(JSON.stringify(results));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
