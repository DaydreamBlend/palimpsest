'use strict';
// Execute the real renderer against a small DOM/API fixture. No backend or model
// calls occur; a separate actual Electron check owns layout and sandbox behavior.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');
function readApplication(name) {
  if (process.env.PALIMPSEST_TEST_ASAR) {
    const { extractFile } = require('../node_modules/@electron/asar/lib/asar.js');
    return extractFile(process.env.PALIMPSEST_TEST_ASAR, path.normalize(name)).toString('utf8');
  }
  return fs.readFileSync(path.join(__dirname, '..', name), 'utf8');
}

class Element {
  constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.attributes = {}; this.handlers = {}; this.dataset = {}; this.style = {}; this.hidden = false; this.className = ''; }
  set textContent(value) { this.children = []; this.text = String(value); }
  get textContent() { return (this.text || '') + this.children.map(child => child.textContent).join(''); }
  set innerHTML(_) { throw new Error('Unsafe HTML insertion'); }
  append(...children) { for (const child of children) { if (child.tagName === '#FRAGMENT') this.children.push(...child.children); else this.children.push(child); } }
  replaceChildren(...children) { this.children = []; this.text = ''; this.append(...children); }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  removeAttribute(key) { delete this.attributes[key]; }
  addEventListener(event, action) { (this.handlers[event] ||= []).push(action); }
  async emit(event) { for (const action of this.handlers[event] || []) await action({ target: this }); }
  async click() { if (!this.disabled) await this.emit('click'); }
  focus() {}
  get childNodes() { return this.children; }
  get childElementCount() { return this.children.length; }
  get classList() { return { toggle: (value, enabled) => { const names = new Set(this.className.split(' ').filter(Boolean)); if (enabled) names.add(value); else names.delete(value); this.className = [...names].join(' '); } }; }
}
function all(element, predicate) { return [element, ...element.children.flatMap(child => all(child, predicate))].filter(predicate); }
function byClass(element, name) { return all(element, item => item.className.split(' ').includes(name)); }
function ui(responses, api = {}) {
  const html = readApplication('index.html');
  const ids = Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(match => [match[1], new Element('div')]));
  const requests = [];
  const document = { getElementById(id) { assert.ok(ids[id], `Missing real HTML id ${id}`); return ids[id]; },
    createElement: tag => new Element(tag), createTextNode: text => { const element = new Element('#text'); element.textContent = text; return element; },
    createDocumentFragment: () => new Element('#fragment'), querySelectorAll: () => [], addEventListener() {} };
  const context = vm.createContext({ document, crypto: webcrypto, window: { palimpsest: { ...api, request: async request => {
    requests.push(JSON.parse(JSON.stringify(request)));
    assert.ok(Object.hasOwn(responses, request.operation), `Unexpected operation ${request.operation}`);
    return typeof responses[request.operation] === 'function' ? responses[request.operation](request) : structuredClone(responses[request.operation]);
  } } }, PdfPanel: class { constructor() { throw new Error('Unexpected PDF load'); } } });
  const source = readApplication('renderer.js').replace(/^import .*?;\r?\n/, '').replace(/boot\(\);\s*$/, '');
  vm.runInContext(source, context, { filename: 'renderer.js' });
  return { ids, requests, run: code => vm.runInContext(code, context) };
}
const REV = '01a0941f-90b3-792b-bd4b-a3e83c18eae1';
const OLD = '01a0941f-90b3-792b-bd4b-a3e83c18eae2';
const EXEC = '01a0941f-90b3-792b-bd4b-a3e83c18eae3';
const I = '01a0941f-90b3-792b-bd4b-a3e83c18eae4';
const D = 'a'.repeat(64);
const origin = { is_inferred: true, origin_operation: 'k2k', origin_record_id: 'record',
  inference_type: 'deduction', derivation_basis: 'Synthetic basis', assumptions: ['Synthetic assumption'], limitations: ['Synthetic limitation'] };
const knowledge = { knode_id: 'k', knode_revision_id: REV, statement: 'Synthetic inferred statement', kind: 'proposition', generation_origin: origin, source_version_status: 'historical', current_applicability: 'needs_revalidation', is_current_now: true };
test('epistemic projection badges distinguish conflicts from truth or missing history', () => {
  const app = ui({});
  const flags = value => app.run(`knowledgeFlags(${JSON.stringify(value)})`).textContent;
  assert.match(flags({ ...knowledge, epistemic_projection: 'contested' }), /상충 주장 있음/);
  assert.match(flags({ ...knowledge, epistemic_projection: 'uncontested' }), /활성 상충 관계 없음/);
  assert.doesNotMatch(flags(knowledge), /상충/);
  assert.doesNotMatch(flags({ ...knowledge, epistemic_projection: 'uncontested' }), /참으로 확정|진실/);
});

test('knowledge navigation opens exact historical premise revisions and keeps origin/version states distinct', async () => {
  const app = ui({ knowledge_catalog: { nodes: [knowledge], sources: [{ data_id: D, title: 'Code fixture', source_format: 'code' }], data_versions: [{ version_id: 'v', data_id: D, is_head: false }] },
    knowledge_node: ({ node_revision_id }) => ({ node: node_revision_id === REV ? knowledge : { ...knowledge, knode_revision_id: OLD, statement: 'Exact old premise', is_current_now: false },
      premise_nodes: node_revision_id === REV ? [{ knode_revision_id: OLD, statement: 'Exact old premise' }] : [], evidence: [] }) });
  await app.ids['knowledge-nav'].click();
  assert.match(app.ids.content.textContent, /추론으로 생성.*현재 Revision.*과거 자료 버전 근거.*전제 재검토 필요/);
  await byClass(app.ids.content, 'knowledge-result')[0].click();
  assert.match(app.ids.content.textContent, /Synthetic assumption/);
  assert.match(app.ids.content.textContent, /Synthetic limitation/);
  await byClass(app.ids.content, 'premise-link')[0].click();
  assert.deepEqual(app.requests.at(-1), { operation: 'knowledge_node', node_revision_id: OLD });
  assert.match(app.ids.content.textContent, /Exact old premise.*과거 Revision/);
  assert.equal(app.ids['knowledge-nav'].attributes['aria-current'], 'page');
});

test('native code evidence opens its owned source execution and renders hostile code as literal text', async () => {
  const quote = '<img src=x onerror="window.injected=true">';
  const app = ui({ knowledge_node: { node: knowledge, evidence: [{ information_id: I, data_id: D, source_execution_id: EXEC, quote, char_start: 0, char_end: quote.length, evidence_basis: 'transitive' }] },
    information: { information_id: I, data_id: D, source_execution_id: EXEC, title: 'module.Parser', kind: 'text', content: quote + '\nreturn value', source_format: 'code',
      original: { media_type: 'text/markdown', sha256: D }, code_context: { member_path: 'src/parser.py', member_text_range: { line_start: 17, line_end: 29 }, enclosing_symbols: [{ qualified_name: 'Parser' }], parse_status: 'parsed' } } });
  await app.run(`openKnowledge('${REV}')`);
  await byClass(app.ids.content, 'evidence-link')[0].click();
  assert.deepEqual(app.requests.at(-1), { operation: 'information', information_id: I, source_execution_id: EXEC });
  assert.match(app.ids['information-view'].textContent, /src\/parser.py.*17–29.*Parser/);
  assert.ok(app.ids['information-view'].textContent.includes(quote));
  assert.equal(all(app.ids['information-view'], node => node.tagName === 'IMG').length, 0);
  assert.equal(all(app.ids['information-view'], node => node.tagName === 'PRE').length, 2);
  assert.equal(app.ids['pdf-tab'].hidden, true);
  assert.equal(app.ids['information-tab'].attributes['aria-selected'], 'true');
});

test('review view preserves unresolved reasons, accepted exact refs and navigable prior executions', async () => {
  const review = { execution_id: EXEC, data_id: D, input_digest: 'frozen-input', state: 'needs_human', next_action: 'resume_review', data_version_mode: 'pinned',
    pending_information_ids: [I], pending_target_ids: ['t'], pending_item_keys: ['item'], sources: [{ data_id: D, source_execution_id: EXEC }], data_versions: [{ version_id: 'v', data_id: D }],
    information: [{ information_id: I, data_id: D, status: 'needs_review', generator_review: { reason: 'Synthetic selection reason' }, validator_review: { reason: 'Unreviewed code branch' } }],
    targets: [{ target_id: 't', data_id: D, status: 'needs_review', validator_review: { reason: 'Missing target content' } }],
    items: [{ target_id: 't', item_key: 'item', label: 'Branch condition', information_id: I, status: 'needs_review', reason: 'Missing item qualification', validator_review: { reason: 'Independent unresolved reason' }, anchors: [] }],
    accepted_knowledge: [{ disposition: 'accepted_new', result_node_revision_id: REV, reason: 'Independent accepted result' }],
    history: [{ execution_id: OLD, state: 'failed', pending_information_ids: [I], accepted_knowledge: [] }],
    model_calls: [{ status: 'failed', phase: 'generator', receipt: { structural_error_code: 'synthetic_structural_error' } }] };
  const app = ui({ review_catalog: { executions: [{ execution_id: EXEC, data_id: D, state: 'needs_human', pending_information_count: 1, pending_target_count: 1, pending_item_count: 1 }] },
    review_status: ({ execution_id }) => ({ ...review, execution_id, history: execution_id === OLD ? [] : review.history }), knowledge_node: { node: knowledge, evidence: [] } });
  await app.ids['reviews-nav'].click();
  await byClass(app.ids.content, 'review-result')[0].click();
  for (const reason of ['Unreviewed code branch', 'Missing target content', 'Missing item qualification', 'Independent unresolved reason', 'synthetic_structural_error']) assert.ok(app.ids.content.textContent.includes(reason), reason);
  assert.match(app.ids.content.textContent, /고정한 과거·비교 범위/);
  assert.match(app.ids.content.textContent, /이 실행 당시/);
  const links = byClass(app.ids.content, 'exact-link');
  await links[1].click();
  assert.deepEqual(app.requests.at(-1), { operation: 'review_status', execution_id: OLD });
  await app.run(`openReview('${EXEC}')`);
  await byClass(app.ids.content, 'exact-link')[0].click();
  assert.deepEqual(app.requests.at(-1), { operation: 'knowledge_node', node_revision_id: REV });
  assert.ok(app.requests.every(row => ['review_catalog', 'review_status', 'knowledge_node'].includes(row.operation)));
});

test('switching navigation ignores an older asynchronous catalog response', async () => {
  let finish;
  const app = ui({ knowledge_catalog: () => new Promise(resolve => { finish = resolve; }), review_catalog: { executions: [] } });
  const pending = app.run('showKnowledge()');
  await app.run('showReviews()');
  finish({ nodes: [knowledge], sources: [], data_versions: [] });
  await pending;
  assert.match(app.ids.content.textContent, /SOURCE REVIEW/);
  assert.doesNotMatch(app.ids.content.textContent, /Synthetic inferred statement/);
});

test('legacy paper-shaped code Wiki pages are labelled as code sources', () => {
  const app = ui({});
  app.run(`renderPage({ page: { kind: 'paper', source_format: 'code', page_id: '${EXEC}', snapshot_id: '${REV}', data_id: '${D}', source_execution_id: '${EXEC}', title: 'Code fixture', items: [{ section: 'methods', text: 'Source declares this behavior.', evidence: [] }] }, current_snapshot_id: '${REV}', history: [], related: {} })`);
  assert.match(app.ids.content.textContent, /CODE \/ LEGACY EXPLANATION/);
  assert.match(app.ids.breadcrumb.textContent, /코드/);
  assert.doesNotMatch(app.ids.content.textContent, /논문/);
  assert.match(app.ids.content.textContent, /구현과 동작/);
  assert.doesNotMatch(app.ids.content.textContent, /연구 방법/);
});

test('Wiki identifies legacy I-based explanations separately from K and new canonical W/P', () => {
  const app = ui({});
  app.run(`state.pages = [{kind:'paper',page_id:'${EXEC}',title:'Retained source explanation',data_id:'${D}'}]; showWikiIndex()`);
  assert.match(app.ids.content.textContent, /WIKI \/ PARCHMENT VIEW/);
  assert.match(app.ids.content.textContent, /기존 I 기반 설명/);
  assert.match(app.ids.content.textContent, /개별 K는 지식 화면/);
  for (const kind of ['paper', 'topic']) {
    const item = { section: 'overview', text: 'Exact legacy explanation text.', evidence: [] };
    const page = { kind, page_id: EXEC, snapshot_id: REV, title: 'Retained explanation',
      ...(kind === 'paper' ? { data_id: D, source_execution_id: EXEC, items: [item] }
        : { contributions: [{ paper_data_id: D, paper_page_id: OLD, paper_title: 'Original paper', items: [item] }] }) };
    app.run(`renderPage(${JSON.stringify({ page, current_snapshot_id: REV, history: [], related: {} })})`);
    assert.match(app.ids.content.textContent, /LEGACY EXPLANATION/);
    assert.match(app.ids.content.textContent, /I 기반 생성 이력과 인용/);
    assert.match(app.ids.content.textContent, /W\/P 식별자를 소급해서 부여하지 않았습니다/);
    assert.match(app.ids.content.textContent, /Exact legacy explanation text\./);
    assert.equal(byClass(app.ids.content, 'article-text').length, 1);
    assert.equal(byClass(app.ids.content, 'citation').length, 0);
  }
  assert.equal(app.requests.length, 0, 'Labels must not generate W/P or mutate old source history');
});

function queryFixture({ version = 2, mixed = false, held = false } = {}) {
  const source = { information_id: I, data_id: D, source_execution_id: EXEC, quote: 'Retained source quote', char_start: 0, char_end: 21 };
  const citation = { node_revision_id: REV, knode_id: 'retained-k', statement: 'Statement saved when answering',
    generation_origin: { ...origin, inference_type: 'deductive', premise_revision_ids: [OLD] },
    retrieval_support: { record_id: 'support-record', records: [{ record_id: 'support-record', operation: 'k2k', derivation: {
      inference_type: 'inductive', premise_revision_ids: [OLD], derivation_basis: 'Separate support basis', assumptions: ['Support assumption'], limitations: ['Support limit'] } }] },
    premise_revisions: [{ node_revision_id: OLD, knode_id: 'premise-k', statement: 'Frozen old premise statement' }],
    direct_groundings: [], transitive_source_refs: [{ ...source, node_revision_id: OLD }] };
  const claim = { claim_key: 'claim', text: '<script>never_execute()</script> Synthetic answer', evidence: version === 1 || mixed ? [source] : [], source_evidence: [] };
  if (version === 2) Object.assign(claim, { knowledge_evidence: [citation], epistemic_basis: mixed ? 'mixed_source_and_accepted_inference' : 'accepted_system_inference' });
  const decision = { claim_key: 'claim', supported: true, citations_sufficient: true, scope_preserved: true, no_new_inference: true, reason: 'Saved independent verdict' };
  if (version === 2) Object.assign(decision, { accepted_inference_faithful: true, inference_limits_preserved: !held });
  return { accepted: !held, job: { query_id: EXEC, question: 'Synthetic question', state: held ? 'needs_review' : 'answered', round: 0 },
    proposal: { schema_version: `wiki-query-answer-v${version}`, claims: [claim] }, validation: { verdict: held ? 'needs_review' : 'accepted', reason: 'Saved validation reason', claims: [decision] }, rounds: [] };
}

test('v2 inferred answer preserves frozen origin, support derivation, premises and exact K citation navigation', async () => {
  const data = queryFixture();
  const app = ui({ knowledge_node: { node: { ...knowledge, statement: 'Current reader exact revision result' }, evidence: [] } });
  app.run(`renderQuery(${JSON.stringify(data)})`);
  const text = app.ids.content.textContent;
  for (const value of ['승인된 시스템 K2K 추론', 'Statement saved when answering', 'Synthetic assumption', 'Synthetic limitation', 'support-record', 'Support assumption', 'Support limit', 'Frozen old premise statement', '전제를 통한 원문 계보']) assert.ok(text.includes(value), value);
  assert.doesNotMatch(text, /원문 기반 답변/);
  assert.doesNotMatch(text, /Current reader exact revision result/);
  assert.equal(byClass(app.ids.content, 'citation').length, 0, 'Do not fabricate a direct source citation for inference');
  assert.equal(all(app.ids.content, element => element.tagName === 'SCRIPT').length, 0);
  assert.ok(text.includes(data.proposal.claims[0].text));
  await byClass(byClass(app.ids.content, 'query-knowledge-citation')[0], 'exact-link')[0].click();
  assert.deepEqual(app.requests.at(-1), { operation: 'knowledge_node', node_revision_id: REV });
});

test('v2 mixed answers show both actual I citations and accepted inference while retaining source ownership', async () => {
  const app = ui({ information: { information_id: I, data_id: D, source_execution_id: EXEC, title: 'Source', kind: 'text', content: 'Retained source quote', original: { media_type: 'text/markdown' } } });
  app.run(`renderQuery(${JSON.stringify(queryFixture({ mixed: true }))})`);
  assert.match(app.ids.content.textContent, /원문 \+ 승인된 시스템 K2K 추론/);
  assert.equal(byClass(app.ids.content, 'citation').length, 1);
  assert.equal(byClass(app.ids.content, 'query-knowledge-citation').length, 1);
  await byClass(app.ids.content, 'evidence-link')[0].click();
  assert.deepEqual(app.requests.at(-1), { operation: 'information', information_id: I, source_execution_id: EXEC });
});

test('held v2 inference stays hidden and failed limit preservation is not labelled confirmed', () => {
  const app = ui({});
  app.run(`renderQuery(${JSON.stringify(queryFixture({ held: true }))})`);
  assert.equal(byClass(app.ids.content, 'query-knowledge-citation').length, 0);
  assert.equal(byClass(app.ids.content, 'article-paper').length, 0);
  assert.equal(byClass(app.ids.content, 'query-status-box').length, 1);
  assert.match(app.ids.content.textContent, /추론 가정·한계 보존 · 검토 필요/);
  assert.doesNotMatch(app.ids.content.textContent, /근거 확인됨/);
  assert.doesNotMatch(app.ids.content.textContent, /Synthetic answer/);
});

test('v1 source-only answers retain existing evidence and need no new inference validation fields', () => {
  const app = ui({});
  app.run(`renderQuery(${JSON.stringify(queryFixture({ version: 1 }))})`);
  assert.match(app.ids.content.textContent, /독립 검증을 통과한 원문 기반 답변/);
  assert.match(app.ids.content.textContent, /근거 확인됨/);
  assert.equal(byClass(app.ids.content, 'citation').length, 1);
  assert.equal(byClass(app.ids.content, 'query-knowledge-citation').length, 0);
  assert.doesNotMatch(app.ids.content.textContent, /K2K 추론|추론 가정·한계 보존/);
});

function informationErrorReview() {
  const sourceExecution = '01a0941f-90b3-792b-bd4b-a3e83c18eae5';
  return { execution_id: EXEC, data_id: D, state: 'needs_human', next_action: 'resume_review',
    sources: [{ data_id: D, source_execution_id: sourceExecution }],
    information: [{ information_id: I, data_id: D, status: 'needs_review',
      generator_review: { reason: 'Existing I review reason' }, validator_review: { reason: 'Existing independent review' } }],
    targets: [{ target_id: 'target', label: 'Existing target', status: 'needs_review',
      validator_review: { reason: 'Existing target remains visible' } }], items: [],
    accepted_knowledge: [{ disposition: 'reused', result_node_revision_id: REV, reason: 'Earlier accepted result stays visible' }],
    history: [{ execution_id: OLD, state: 'failed', accepted_knowledge: [], pending_information_ids: [I] }],
    information_errors: { schema_version: 'i2k-information-errors-v1', execution_id: EXEC,
      requires_user_review: true, d2i_calls: 0, direct_source_compilation_allowed: false,
      errors: [{ reported_by: 'generator', source_request_id: OLD, data_id: D,
        source_execution_id: sourceExecution, source_profile_id: REV, source_input_sha256: 'b'.repeat(64),
        information_ids: [I], source_refs: [{ information_id: I,
          source_refs: [{ block_id: '/file/function', locator_type: 'text_range', text_range: { char_start: 40, char_end: 90 } }] }],
        reason_codes: ['d2i_information_error'], reason: 'Reported <img src=x onerror="injected()"> structure concern.',
        status: 'reported_error', verification_status: 'verification_pending' }] } };
}

test('D2I information errors remain pending user reports with exact I navigation and previous review history', async () => {
  const review = informationErrorReview(), error = review.information_errors.errors[0];
  const app = ui({ review_status: review, information: { information_id: I, data_id: D,
    source_execution_id: error.source_execution_id, kind: 'text', title: 'Retained I', content: 'Original retained Information',
    original: { media_type: 'text/markdown', sha256: D }, media: [] } });
  await app.run(`openReview('${EXEC}')`);
  const section = byClass(app.ids.content, 'information-errors')[0];
  for (const value of ['D2I 정보 오류 · 사용자 확인 필요', '관련 K 보류 · D2I 자동 재실행 없음 · 원문에서 K 우회 생성 없음',
    '생성 모델 보고', '보고된 오류', '사실 확인 대기', D, I, error.source_execution_id, error.source_profile_id,
    error.source_input_sha256, error.reason, '/file/function']) assert.ok(section.textContent.includes(value), value);
  for (const value of ['Existing I review reason', 'Existing independent review', 'Existing target remains visible',
    'Earlier accepted result stays visible', OLD]) assert.ok(app.ids.content.textContent.includes(value), value);
  assert.equal(all(section, element => ['IMG', 'SCRIPT'].includes(element.tagName)).length, 0);
  await byClass(section, 'evidence-link')[0].click();
  assert.deepEqual(app.requests.at(-1), { operation: 'information', information_id: I, source_execution_id: error.source_execution_id });
  assert.notEqual(error.source_execution_id, review.execution_id);
  assert.ok(app.requests.every(row => ['review_status', 'information'].includes(row.operation)));
});

test('ordinary missing_material_content remains a review issue without a D2I error banner', () => {
  const review = informationErrorReview();
  review.information[0].validator_review.reason = 'missing_material_content: further semantic review is needed';
  review.information_errors.errors = [];
  review.information_errors.requires_user_review = false;
  const app = ui({});
  app.run(`renderReview(${JSON.stringify(review)})`);
  assert.equal(byClass(app.ids.content, 'information-errors').length, 0);
  assert.match(app.ids.content.textContent, /missing_material_content/);
  assert.doesNotMatch(app.ids.content.textContent, /D2I 정보 오류 · 사용자 확인 필요/);
  delete review.information_errors;
  app.run(`renderReview(${JSON.stringify(review)})`);
  assert.equal(byClass(app.ids.content, 'information-errors').length, 0);
});

test('reported information errors never create an I reader link from malformed IDs or Data ownership text', () => {
  for (const change of [{ information_ids: [I.replace('-792b-', '-492b-')] },
    { information_ids: [null] }, { source_execution_id: EXEC.toUpperCase() },
    { source_execution_id: null }, { data_id: '../original.txt' }]) {
    const review = informationErrorReview();
    Object.assign(review.information_errors.errors[0], change);
    const app = ui({});
    app.run(`renderReview(${JSON.stringify(review)})`);
    const section = byClass(app.ids.content, 'information-errors')[0];
    assert.equal(byClass(section, 'evidence-link').length, 0, JSON.stringify(change));
    assert.match(section.textContent, /읽기 연결을 확인해야 합니다/);
    assert.equal(app.requests.length, 0);
  }
});

test('an error report bound to another execution is not presented as this review error', () => {
  const review = informationErrorReview();
  review.information_errors.execution_id = OLD;
  const app = ui({});
  app.run(`renderReview(${JSON.stringify(review)})`);
  assert.equal(byClass(app.ids.content, 'information-errors').length, 0);
  assert.match(app.ids.content.textContent, /이 실행과 정보 오류 보고의 연결을 확인하지 못했습니다/);
  assert.match(app.ids.content.textContent, /Existing I review reason/);
});

test('a contradictory confirmed validator verdict stays an unverified D2I error report with K held', () => {
  const review = informationErrorReview();
  Object.assign(review.information_errors.errors[0], { reported_by: 'validator', source_request_id: null,
    review_verdict: 'confirmed', contradictory_verdict: true, reason: 'Contradictory saved review response' });
  const app = ui({});
  app.run(`renderReview(${JSON.stringify(review)})`);
  const section = byClass(app.ids.content, 'information-errors')[0];
  assert.match(section.textContent, /독립 검토 모델 보고/);
  assert.match(section.textContent, /사실 확인 대기/);
  assert.match(section.textContent, /판정과 D2I 오류 코드가 충돌합니다/);
  assert.match(section.textContent, /관련 K는 확인이 끝날 때까지 보류/);
  assert.doesNotMatch(section.textContent, /오류 확정|누락 확인됨|검증 통과/);
});

test('inconsistent processing flags do not produce a false no-reparse assurance', () => {
  const review = informationErrorReview();
  review.information_errors.d2i_calls = 1;
  const app = ui({});
  app.run(`renderReview(${JSON.stringify(review)})`);
  const section = byClass(app.ids.content, 'information-errors')[0];
  assert.match(section.textContent, /자동 처리 금지 상태를 확인하지 못했습니다/);
  assert.doesNotMatch(section.textContent, /D2I 자동 재실행 없음/);
});

function dataEvidenceFixture(pdf = false) {
  const quote = '<img src=x onerror="neverExecute()">';
  const grounding = { grounding_type: 'data', grounding_id: I, node_revision_id: REV,
    origin_record_id: EXEC, view_id: OLD, data_id: D, representation: 'original_utf8_excerpt',
    char_start: 1, char_end: 1 + quote.length, quote, media_sha256: null,
    locator: { byte_start: 102, byte_end: 102 + quote.length, char_start: 51, char_end: 51 + quote.length, line_start: 7, line_end: 7 } };
  const response = { grounding, view: { kind: 'text', view_id: OLD, data_id: D, text: 'μ' + quote + '\r\nfollowing',
    locator: { byte_start: 100, byte_end: 200, char_start: 50, char_end: 150, line_start: 7, line_end: 8 } },
    source_info: null, media_kind: 'text', preparation_id: EXEC,
    original: { sha256: D, byte_size: 300, media_type: 'text/plain' }, read_only: true };
  if (pdf) {
    Object.assign(grounding, { representation: 'original_pdf_page_image', quote: '', char_start: 0, char_end: 0, media_sha256: 'b'.repeat(64),
      locator: { page_index: 0, page_count: 2, coordinate_system: 'pdf_points_top_left' } });
    response.view = { kind: 'pdf_page', view_id: OLD, data_id: D, image_sha256: grounding.media_sha256, page_index: 0, page_count: 2 };
    response.media_kind = 'pdf'; response.original.media_type = 'application/pdf';
    response.image = { sha256: grounding.media_sha256, media_type: 'image/png', byte_size: 3, base64: 'YWJj' };
  }
  return response;
}

test('D2K-origin knowledge opens literal D text with no fabricated Information or D2I request', async () => {
  const reply = dataEvidenceFixture();
  const app = ui({ knowledge_node: { node: { ...knowledge, generation_origin: { origin_operation: 'd2k', is_inferred: false, origin_record_id: EXEC } },
    evidence: [], data_evidence: [reply.grounding] }, data_grounding: reply });
  await app.run(`openKnowledge('${REV}')`);
  assert.match(app.ids.content.textContent, /D2K · 원문 D에서 생성/);
  await byClass(app.ids.content, 'data-evidence-link')[0].click();
  assert.deepEqual(app.requests.at(-1), { operation: 'data_grounding', grounding_id: I });
  assert.equal(app.ids['information-tab'].textContent, '원문 D');
  assert.equal(app.ids['pdf-tab'].hidden, true);
  assert.equal(all(app.ids['information-view'], node => node.tagName === 'IMG').length, 0);
  assert.equal(all(app.ids['information-view'], node => node.tagName === 'MARK')[0].textContent, reply.grounding.quote);
  assert.match(app.ids['information-view'].textContent, /인용 원본 bytes\[102,/);
  assert.match(app.ids['information-view'].textContent, /보존한 원문 범위bytes \[100, 200\)/);
  assert.ok(app.requests.every(row => ['knowledge_node', 'data_grounding'].includes(row.operation)));
});

test('I-free PDF D2K evidence displays the retained page image without using the native PDF or I reader', async () => {
  const reply = dataEvidenceFixture(true);
  const app = ui({ data_grounding: reply });
  await app.run(`openEvidence(${JSON.stringify(reply.grounding)})`);
  assert.equal(app.requests.length, 1);
  assert.equal(app.requests[0].operation, 'data_grounding');
  const image = all(app.ids['information-view'], node => node.tagName === 'IMG')[0];
  assert.equal(image.src, 'data:image/png;base64,YWJj');
  assert.match(image.alt, /PDF 1페이지/);
  assert.match(app.ids['information-view'].textContent, /원본 PDF에서 보존한 페이지 이미지/);
  assert.equal(app.ids['pdf-tab'].hidden, true);
});

test('D2K reader refuses mismatched Data and preserves the source request race boundary', async () => {
  const reply = dataEvidenceFixture();
  let finish;
  const app = ui({ data_grounding: () => new Promise(resolve => { finish = resolve; }) });
  const pending = app.run(`openDataEvidence(${JSON.stringify(reply.grounding)})`);
  app.run('closeSource()');
  finish(reply); await pending;
  assert.equal(app.ids['source-panel'].hidden, true);
  const invalid = { ...reply, original: { ...reply.original, sha256: 'f'.repeat(64) } };
  const other = ui({ data_grounding: invalid });
  await other.run(`openDataEvidence(${JSON.stringify(reply.grounding)})`);
  assert.match(other.ids['source-status'].textContent, /결속이 일치하지 않습니다/);
  assert.ok(!other.ids['information-view'].textContent.includes(reply.grounding.quote));
});

test('v3 source-created D2K query uses exact Data evidence and keeps held answers hidden', async () => {
  const reply = dataEvidenceFixture();
  const data = queryFixture({ version: 1 });
  data.proposal.schema_version = 'wiki-query-answer-v3';
  Object.assign(data.proposal.claims[0], { evidence: [], knowledge_evidence: [], data_evidence: [reply.grounding], epistemic_basis: 'direct_source' });
  Object.assign(data.validation.claims[0], { accepted_inference_faithful: true, inference_limits_preserved: true });
  const app = ui({ data_grounding: reply });
  app.run(`renderQuery(${JSON.stringify(data)})`);
  assert.match(app.ids.content.textContent, /D2K 원문 직접 근거/);
  assert.equal(byClass(app.ids.content, 'query-knowledge-citation').length, 0);
  assert.equal(byClass(app.ids.content, 'citation').length, 0);
  await byClass(app.ids.content, 'data-evidence-link')[0].click();
  assert.deepEqual(app.requests.at(-1), { operation: 'data_grounding', grounding_id: I });
  data.accepted = false; data.job.state = 'needs_review';
  app.run(`renderQuery(${JSON.stringify(data)})`);
  assert.equal(byClass(app.ids.content, 'query-data-citation').length, 0);
  assert.equal(byClass(app.ids.content, 'article-paper').length, 0);
});

const STORE_A = '01a0941f-90b3-792b-bd4b-a3e83c18ea01';
const STORE_B = '01a0941f-90b3-792b-bd4b-a3e83c18ea02';
const REALM = '01a0941f-90b3-792b-bd4b-a3e83c18ea03';
const SERIES = '01a0941f-90b3-792b-bd4b-a3e83c18ea04';
const storesFixture = () => [
  { store_id: STORE_A, label: 'Alpha', connected: true, hasWiki: false, hasQueries: false },
  { store_id: STORE_B, label: 'Beta', connected: true, hasWiki: true, hasQueries: true },
];
function registeredFixture(storeId, changes = {}) {
  return { store_id: storeId, data_id: D, filename: `${storeId === STORE_A ? 'Alpha' : 'Beta'} source.md`,
    source_kind: 'markdown', media_type: 'text/markdown', byte_size: 100, information_count: 1, source_execution_count: 1,
    versions: [], ...changes };
}
function sourceDetailFixture(storeId, changes = {}) {
  return { data: registeredFixture(storeId), executions: [{ execution_id: EXEC, state: 'completed', profile: { transformation: { algorithm: 'markdown-groups-v1' } } }],
    information: [{ data_id: D, information_id: I, source_execution_id: EXEC, title: `${storeId === STORE_A ? 'Alpha' : 'Beta'} Information`, kind: 'text',
      character_count: 20, source_refs: [{ locator_type: 'text_range', text_range: { byte_start: 0, byte_end: 20, line_start: 1, line_end: 2 } }] }],
    knowledge: [{ ...knowledge, statement: `${storeId === STORE_A ? 'Alpha' : 'Beta'} Knowledge`, groundings: [] }],
    versions: [], acquisitions: [], ...changes };
}
function sourceInformationFixture(storeId, changes = {}) {
  return { information_id: I, data_id: D, source_execution_id: EXEC, title: `${storeId === STORE_A ? 'Alpha' : 'Beta'} Information`, kind: 'text',
    content: `${storeId === STORE_A ? 'ALPHA' : 'BETA'} exact μ source\r\nSecond line.`, source_format: 'markdown', media: [],
    source_refs: [{ locator_type: 'text_range', text_range: { byte_start: 0, byte_end: 36, line_start: 1, line_end: 2 } }],
    original: { media_type: 'text/markdown', sha256: D, byte_size: 36 }, ...changes };
}
function unifiedState(app, changes = {}) {
  app.run(`Object.assign(state, ${JSON.stringify({ unified: true, stores: storesFixture(), storeId: STORE_A, mode: 'data',
    data: [registeredFixture(STORE_A), registeredFixture(STORE_B)], ...changes })})`);
}
function inspect(app, expression) { return JSON.parse(app.run(`JSON.stringify(${expression})`)); }

test('unified startup reconnects initial disconnected stores before catalog discovery', async () => {
  const stores = storesFixture().map(store => ({ ...store, connected: false }));
  const reconnected = [];
  const app = ui({ source_catalog: ({ store_id }) => ({ data: [registeredFixture(store_id)] }), catalog: { pages: [] }, queries: { queries: [] }, parchment_catalog: { parchments: [], supported: false } }, {
    stores: async () => structuredClone(stores), reconnect: async id => { reconnected.push(id); stores.find(store => store.store_id === id).connected = true; },
  });
  await app.run('bootUnified(false)');
  assert.deepEqual(reconnected, [STORE_A, STORE_B]);
  assert.deepEqual(app.requests.filter(request => request.operation === 'source_catalog').map(request => request.store_id), [STORE_A, STORE_B]);
  assert.deepEqual(app.requests.filter(request => request.operation === 'parchment_catalog').map(request => request.store_id), [STORE_A, STORE_B], 'P discovery includes stores without a legacy Wiki');
  assert.equal(inspect(app, 'state.data.length'), 2);
  assert.equal(byClass(app.ids.content, 'data-card').length, 1);
  assert.match(app.ids['connection-label'].textContent, /2\/2/);
});

test('unified partial store or wiki failure preserves available raw Data and exposes the issue', async () => {
  const stores = storesFixture();
  const app = ui({ source_catalog: ({ store_id }) => { if (store_id === STORE_A) throw new Error('source_database_unavailable'); return { data: [registeredFixture(store_id)] }; },
    catalog: () => { throw new Error('wiki_database_unavailable'); }, queries: { queries: [] }, parchment_catalog: { parchments: [], supported: false } }, { stores: async () => structuredClone(stores) });
  await app.run('bootUnified(false)');
  assert.equal(byClass(app.ids.content, 'data-card').length, 1);
  assert.match(app.ids.content.textContent, /Beta source/);
  assert.match(app.ids.notice.textContent, /Alpha.*source_database_unavailable/);
  assert.match(app.ids.notice.textContent, /Beta.*wiki_database_unavailable/);
  assert.equal(inspect(app, 'state.pages.length'), 0);
});

test('duplicate Data groups retain qualified locations for Wiki, exact I and K navigation', async () => {
  const app = ui({ source_detail: ({ store_id }) => sourceDetailFixture(store_id),
    source_information: ({ store_id }) => sourceInformationFixture(store_id),
    knowledge_node: ({ store_id }) => ({ node: { ...knowledge, statement: `${store_id === STORE_A ? 'Alpha' : 'Beta'} selected K` }, evidence: [] }) });
  unifiedState(app, { pages: [{ store_id: STORE_B, kind: 'paper', page_id: OLD, data_id: D, title: 'Beta source Wiki' }] });
  app.run('showData()');
  assert.equal(byClass(app.ids.content, 'data-card').length, 1);
  assert.match(app.ids.content.textContent, /2개 보존 위치/);
  await byClass(app.ids.content, 'data-title')[0].click();
  assert.deepEqual(app.requests.at(-1), { operation: 'source_detail', data_id: D, store_id: STORE_B });
  await byClass(app.ids.content, 'source-information-link')[0].click();
  assert.deepEqual(app.requests.at(-1), { operation: 'source_information', data_id: D, information_id: I, source_execution_id: EXEC, store_id: STORE_B });
  assert.match(app.ids['information-view'].textContent, /BETA exact μ source/);
  await all(app.ids.content, element => element.tagName === 'BUTTON' && element.textContent === '지식과 생성 근거 열기')[0].click();
  assert.deepEqual(app.requests.at(-1), { operation: 'knowledge_node', node_revision_id: REV, store_id: STORE_B });
  assert.match(app.ids.content.textContent, /Beta selected K/);
  await app.run(`openData('${STORE_A}', '${D}')`);
  await byClass(app.ids.content, 'source-information-link')[0].click();
  assert.equal(app.requests.at(-1).store_id, STORE_A);
  assert.match(app.ids['information-view'].textContent, /ALPHA exact μ source/);
  assert.doesNotMatch(app.ids['information-view'].textContent, /BETA exact/);
});

test('late source detail from another store cannot replace the same-hash selected location', async () => {
  let finish;
  const app = ui({ source_detail: ({ store_id }) => store_id === STORE_A ? new Promise(resolve => { finish = resolve; }) : sourceDetailFixture(STORE_B) });
  unifiedState(app);
  const pending = app.run(`openData('${STORE_A}', '${D}')`);
  await app.run(`openData('${STORE_B}', '${D}')`);
  finish(sourceDetailFixture(STORE_A)); await pending;
  assert.equal(inspect(app, 'state.storeId'), STORE_B);
  assert.match(app.ids.content.textContent, /Beta source/);
  assert.doesNotMatch(app.ids.content.textContent, /Alpha Information|Alpha Knowledge/);
});

test('late exact Information and media from a switched store do not leak into the source pane', async () => {
  let finish;
  const app = ui({ source_information: ({ store_id }) => store_id === STORE_A ? new Promise(resolve => { finish = resolve; }) : sourceInformationFixture(STORE_B) });
  unifiedState(app);
  const evidence = { sourceOnly: true, data_id: D, information_id: I, source_execution_id: EXEC };
  const pending = app.run(`openEvidence(${JSON.stringify({ ...evidence, store_id: STORE_A })})`);
  await app.run(`openEvidence(${JSON.stringify({ ...evidence, store_id: STORE_B })})`);
  finish(sourceInformationFixture(STORE_A, { media: [{ sha256: 'b'.repeat(64), byte_size: 3 }] })); await pending;
  assert.equal(inspect(app, 'state.information.store_id'), STORE_B);
  assert.match(app.ids['information-view'].textContent, /BETA exact/);
  assert.doesNotMatch(app.ids['information-view'].textContent, /ALPHA exact/);
  assert.equal(app.requests.filter(request => request.operation === 'source_artifact').length, 0);
});

test('source-only HTML is exact literal text with no legacy Wiki or browser request', async () => {
  const raw = '\ufeff<script>window.injected=true</script>\r\n<img src=https://example.invalid/private>μ';
  const app = ui({ source_artifact: { data_id: D, sha256: D, media_type: 'text/html', byte_size: Buffer.byteLength(raw), text: raw, verified: true } });
  unifiedState(app);
  await app.run(`openOriginalData('${STORE_A}', ${JSON.stringify(registeredFixture(STORE_A, { media_type: 'text/html', source_kind: 'web' }))})`);
  assert.ok(app.ids['information-view'].textContent.includes(raw));
  assert.equal(all(app.ids['information-view'], element => ['SCRIPT', 'IMG', 'IFRAME'].includes(element.tagName)).length, 0);
  assert.deepEqual(app.requests, [{ operation: 'source_artifact', data_id: D, store_id: STORE_A }]);
});

test('source-only PDF directory resolves stored zero-based page_index to visible page number', async () => {
  const detail = sourceDetailFixture(STORE_A);
  detail.information[0].source_refs = [{ page_index: 5, bbox: [0, 0, 50, 50] }];
  const app = ui({ source_detail: detail, source_information: sourceInformationFixture(STORE_A, {
    original: { media_type: 'application/pdf', sha256: D }, source_format: 'pdf', source_refs: detail.information[0].source_refs }) });
  unifiedState(app);
  await app.run(`openData('${STORE_A}', '${D}')`);
  await byClass(app.ids.content, 'source-information-link')[0].click();
  assert.deepEqual(inspect(app, 'state.evidence.page_numbers'), [6]);
  assert.equal(inspect(app, 'state.pdfPage'), 6);
  assert.match(app.ids['information-view'].textContent, /6 페이지/);
});

test('non-PDF exact Information shows retained text location without inventing page one', async () => {
  const app = ui({ source_information: sourceInformationFixture(STORE_A) });
  unifiedState(app);
  await app.run(`openEvidence(${JSON.stringify({ sourceOnly: true, store_id: STORE_A, data_id: D, information_id: I, source_execution_id: EXEC })})`);
  assert.equal(app.ids['pdf-tab'].hidden, true);
  assert.doesNotMatch(app.ids['information-view'].textContent, /1 페이지/);
  assert.match(app.ids['information-view'].textContent, /line_start/);
  assert.ok(app.ids['information-view'].textContent.includes(sourceInformationFixture(STORE_A).content));
});

function realmFixture(changes = {}) {
  return { realm_id: REALM, revision_id: REV, revision_no: 1, name: 'Research', description: 'Retained workspace scope',
    members: [{ store_id: STORE_A, member_kind: 'data', member_id: D }], ...changes };
}
test('Realm data and series filters stay store-qualified even for duplicate Data hashes', () => {
  const second = 'b'.repeat(64), third = 'c'.repeat(64);
  const app = ui({});
  unifiedState(app, { data: [registeredFixture(STORE_A), registeredFixture(STORE_B, { versions: [{ series_id: SERIES }] }),
    registeredFixture(STORE_B, { data_id: second, versions: [{ series_id: SERIES }] }), registeredFixture(STORE_A, { data_id: third })],
    realms: [realmFixture(), realmFixture({ realm_id: OLD, name: 'Series', members: [{ store_id: STORE_B, member_kind: 'data_series', member_id: SERIES }] })] });
  app.run(`state.realmId='${REALM}'`);
  assert.deepEqual(inspect(app, 'groupedData().flatMap(group => group.locations.map(source => source.store_id))'), [STORE_A]);
  app.run(`state.realmId='${OLD}'`);
  assert.deepEqual(inspect(app, 'groupedData().map(group => group.data_id)'), [D, second]);
  assert.deepEqual(inspect(app, 'groupedData().flatMap(group => group.locations.map(source => source.store_id))'), [STORE_B, STORE_B]);
  app.run("state.realmId='unassigned'");
  assert.deepEqual(inspect(app, 'groupedData().map(group => group.data_id)'), [third]);
  app.run("state.realmId='all';state.dataFilter='web'");
  assert.deepEqual(inspect(app, 'groupedData()'), []);
});

test('Realm membership revision sends exact CAS, reason and store-qualified members while preserving unavailable refs', async () => {
  const sent = [], unavailable = { store_id: EXEC, member_kind: 'data', member_id: 'd'.repeat(64) };
  const realm = realmFixture({ members: [unavailable] });
  const app = ui({}, { realms: async request => { sent.push(structuredClone(request)); throw new Error('realm_revision_changed'); } });
  unifiedState(app, { data: [registeredFixture(STORE_A), registeredFixture(STORE_B, { versions: [{ series_id: SERIES, series_name: 'Code history' }] })], realms: [realm] });
  app.run(`renderRealmEditor($('content'), ${JSON.stringify(realm)}, state.pageTicket)`);
  const rows = byClass(app.ids.content, 'realm-member');
  const seriesRow = rows.find(row => row.textContent.includes('Code history'));
  const box = all(seriesRow, element => element.tagName === 'INPUT')[0]; box.checked = true; await box.emit('change');
  const fields = byClass(app.ids.content, 'realm-input'); fields[2].value = 'Keep the exact selected source series.';
  const save = byClass(app.ids.content, 'realm-save')[0]; await save.click(); await save.click();
  assert.equal(sent.length, 2);
  assert.equal(sent[0].operation, 'revise');
  assert.equal(sent[0].expected_revision_id, REV);
  assert.equal(sent[0].realm_id, REALM);
  assert.equal(sent[0].actor, 'desktop-user');
  assert.equal(sent[0].reason, fields[2].value);
  assert.deepEqual(sent[0].members, [unavailable, { store_id: STORE_B, member_kind: 'data_series', member_id: SERIES }]);
  assert.equal(sent[0].request_id, sent[1].request_id);
  assert.match(sent[0].request_id, /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.deepEqual(inspect(app, 'state.realms'), [realm]);
  assert.match(app.ids.content.textContent, /realm_revision_changed/);
  fields[2].value = 'Changed operator explanation'; await save.click();
  assert.notEqual(sent[2].request_id, sent[1].request_id);
  assert.equal(sent[2].expected_revision_id, REV);
});

test('Realm creation requires operator name and reason and never invents initial memberships', async () => {
  const sent = [], created = realmFixture({ members: [] });
  const app = ui({}, { realms: async request => { sent.push(structuredClone(request)); return structuredClone(created); } });
  unifiedState(app);
  app.run("renderRealmEditor($('content'), undefined, state.pageTicket)");
  const fields = byClass(app.ids.content, 'realm-input');
  const save = byClass(app.ids.content, 'realm-save')[0]; await save.click();
  assert.equal(sent.length, 0);
  fields[0].value = 'Research'; fields[1].value = '<script>literal metadata</script>'; fields[2].value = 'Separate this research context.';
  await save.click();
  assert.equal(sent.length, 1);
  assert.equal(sent[0].operation, 'create');
  assert.equal(sent[0].description, '<script>literal metadata</script>');
  assert.ok(!Object.hasOwn(sent[0], 'members'));
  assert.ok(!Object.hasOwn(sent[0], 'expected_revision_id'));
  assert.equal(all(app.ids.content, element => element.tagName === 'SCRIPT').length, 0);
  assert.equal(inspect(app, 'state.realms[0].realm_id'), REALM);
});

test('late initial Realm catalog cannot overwrite a newer navigation state', async () => {
  let finish, started;
  const waiting = new Promise(resolve => { started = resolve; });
  const app = ui({ source_catalog: { data: [] }, catalog: { pages: [] }, queries: { queries: [] }, parchment_catalog: { parchments: [], supported: false } }, {
    stores: async () => storesFixture(), realms: () => { started(); return new Promise(resolve => { finish = resolve; }); },
  });
  const pending = app.run('bootUnified(false)'); await waiting;
  const latest = realmFixture({ revision_id: OLD, revision_no: 2, name: 'Newer accepted Realm view' });
  app.run(`state.realms=${JSON.stringify([latest])};showData()`);
  finish({ realms: [realmFixture()] }); await pending;
  assert.deepEqual(inspect(app, 'state.realms'), [latest]);
});

test('aggregated review cards retain each store title when source hashes collide', async () => {
  const app = ui({ review_catalog: () => ({ executions: [{ execution_id: EXEC, data_id: D, state: 'needs_human' }] }) });
  unifiedState(app, { stores: storesFixture().map(store => ({ ...store, hasWiki: true })) });
  await app.run('showReviews()');
  const cards = byClass(app.ids.content, 'review-result');
  assert.equal(cards.length, 2);
  assert.match(cards[0].textContent, /Alpha source/);
  assert.match(cards[1].textContent, /Beta source/);
});

test('an earlier Realm save cannot replace a different editor selected while saving', async () => {
  const first = realmFixture(), second = realmFixture({ realm_id: OLD, revision_id: EXEC, name: 'Second Realm', members: [] });
  let finish;
  const app = ui({}, { realms: request => request.operation === 'catalog' ? Promise.resolve({ realms: [first, second] })
    : new Promise(resolve => { finish = resolve; }) });
  unifiedState(app);
  await app.run('showRealmManager()');
  const picker = byClass(app.ids.content, 'realm-picker')[0];
  picker.value = REALM; await picker.emit('change');
  byClass(app.ids.content, 'realm-input')[2].value = 'Save the first Realm.';
  const pending = byClass(app.ids.content, 'realm-save')[0].click();
  picker.value = OLD; await picker.emit('change');
  byClass(app.ids.content, 'realm-input')[2].value = 'Unsaved second Realm explanation';
  finish({ ...first, revision_id: I, revision_no: 2 }); await pending;
  const fields = byClass(app.ids.content, 'realm-input');
  assert.equal(fields[0].value, 'Second Realm');
  assert.equal(fields[2].value, 'Unsaved second Realm explanation');
});

test('the selected Realm persists across Wiki, K, review and saved question lists', async () => {
  const app = ui({ knowledge_catalog: ({ store_id }) => ({ nodes: [{ ...knowledge, statement: store_id, source_data_ids: [D] }], sources: [] }),
    review_catalog: ({ store_id }) => ({ executions: [{ execution_id: EXEC, data_id: D, source_data_ids: [D], state: 'prepared', label: store_id }] }) });
  unifiedState(app, { realms: [realmFixture()], realmId: REALM, stores: storesFixture().map(store => ({ ...store, hasWiki: true })),
    pages: [STORE_A, STORE_B].map(store_id => ({ store_id, page_id: OLD, kind: 'paper', data_id: D, source_data_ids: [D], title: store_id })),
    queries: [STORE_A, STORE_B].map(store_id => ({ store_id, query_id: OLD, question: store_id, state: 'answered', source_data_ids: [D] })) });
  await app.run('showWikiIndex()');
  assert.equal(byClass(app.ids.content, 'wiki-result').length, 1);
  assert.ok(app.ids.content.textContent.includes(STORE_A));
  assert.ok(!app.ids.content.textContent.includes(STORE_B));
  await app.run('showKnowledge()'); assert.equal(byClass(app.ids.content, 'knowledge-result').length, 1);
  await app.run('showReviews()'); assert.equal(byClass(app.ids.content, 'review-result').length, 1);
  await app.run('showQueries()'); assert.equal(byClass(app.ids.content, 'query-card').length, 1);
  assert.equal(app.ids['realm-controls'].hidden, false);
  assert.equal(app.ids['active-realm'].textContent, 'Research');
  assert.equal(inspect(app, 'state.realmId'), REALM);
});

test('global K includes a connected source-only store', async () => {
  const app = ui({ knowledge_catalog: ({ store_id }) => ({ nodes: [{ ...knowledge, statement: store_id,
    source_data_ids: [D] }], sources: [], data_versions: [] }) });
  unifiedState(app, { realms: [realmFixture()], realmId: REALM });
  await app.run('showKnowledge()');
  assert.equal(byClass(app.ids.content, 'knowledge-result').length, 1);
  assert.match(app.ids.content.textContent, new RegExp(STORE_A));
  assert.deepEqual(app.requests.filter(row => row.operation === 'knowledge_catalog'), [
    { operation: 'knowledge_catalog', store_id: STORE_A },
    { operation: 'knowledge_catalog', store_id: STORE_B },
  ]);
});

test('direct assignment binds every known copy of one Data and preserves unrelated membership', async () => {
  const sent = [], unrelated = { store_id: STORE_A, member_kind: 'data', member_id: 'b'.repeat(64) };
  const realm = realmFixture({ members: [unrelated] }), other = realmFixture({ realm_id: OLD, name: 'Other Realm' });
  const app = ui({}, { realms: async payload => {
    if (payload.operation === 'catalog') return { realms: [other, realm] };
    sent.push(structuredClone(payload)); return { ...realm, members: payload.members, revision_id: OLD, revision_no: 2 };
  } });
  unifiedState(app, { realms: [realm] });
  await app.run(`openAssignment(${JSON.stringify(registeredFixture(STORE_A))})`);
  const selector = byClass(app.ids['assignment-body'], 'assignment-realm')[0]; selector.value = REALM; await selector.emit('change');
  await byClass(app.ids['assignment-body'], 'realm-save')[0].click();
  assert.equal(sent.length, 1); assert.equal(sent[0].expected_revision_id, REV);
  assert.deepEqual(sent[0].members, [unrelated, { store_id: STORE_A, member_kind: 'data', member_id: D }, { store_id: STORE_B, member_kind: 'data', member_id: D }]);
  assert.equal(sent[0].actor, 'desktop-user');
  assert.match(sent[0].request_id, /^[0-9a-f-]{14}7/);
  assert.equal(inspect(app, `state.realms.find(realm => realm.realm_id === '${REALM}').revision_id`), OLD);
  assert.equal(byClass(app.ids['assignment-body'], 'assignment-realm')[0].value, REALM);
  assert.equal(byClass(app.ids['assignment-body'], 'realm-save')[0].disabled, true);
  assert.equal(app.requests.length, 0);
});

test('removing direct Data membership keeps inherited series and every other member', async () => {
  const inherited = { store_id: STORE_A, member_kind: 'data_series', member_id: SERIES };
  const realm = realmFixture({ members: [...realmFixture().members, inherited] }), sent = [];
  const source = registeredFixture(STORE_A, { versions: [{ series_id: SERIES, series_name: 'Code versions' }] });
  const app = ui({}, { realms: async payload => { if (payload.operation === 'catalog') return { realms: [realm] };
    sent.push(structuredClone(payload)); return { ...realm, members: payload.members, revision_id: OLD, revision_no: 2 }; } });
  unifiedState(app, { realms: [realm], data: [source] });
  await app.run(`openAssignment(${JSON.stringify(source)})`);
  await byClass(app.ids['assignment-body'], 'realm-remove')[0].click();
  assert.deepEqual(sent[0].members, [inherited]);
  assert.match(app.ids['assignment-body'].textContent, /자료 계열을 통해서도 소속/);
  assert.equal(byClass(app.ids['assignment-body'], 'realm-remove')[0].disabled, true);
});

test('assignment conflict retries its exact request without pretending the membership changed', async () => {
  const realm = realmFixture({ members: [] }), sent = [];
  const app = ui({}, { realms: async payload => { if (payload.operation === 'catalog') return { realms: [realm] };
    sent.push(structuredClone(payload)); throw new Error('realm_revision_changed'); } });
  unifiedState(app);
  await app.run(`openAssignment(${JSON.stringify(registeredFixture(STORE_A))})`);
  const add = byClass(app.ids['assignment-body'], 'realm-save')[0]; await add.click(); await add.click();
  assert.equal(sent[0].request_id, sent[1].request_id); assert.equal(sent[1].expected_revision_id, REV);
  assert.deepEqual(inspect(app, 'state.realms[0].members'), []);
  assert.match(app.ids['assignment-body'].textContent, /realm_revision_changed/);
});

test('the Data view exposes stored K first and labels a prepared zero-call I2K honestly', async () => {
  const detail = sourceDetailFixture(STORE_A);
  detail.i2k_executions = [{ execution_id: EXEC, state: 'prepared', successful_model_calls: 0, created_or_revised_nodes: 0, reused_records: 0 }];
  const app = ui({ source_detail: detail }); unifiedState(app);
  await app.run(`openData('${STORE_A}', '${D}')`);
  assert.equal(byClass(app.ids.content, 'detail-knowledge')[0].hidden, false);
  assert.match(app.ids.content.textContent, /I2K 모델 미실행/);
  assert.match(app.ids.content.textContent, /성공한 모델 호출 0회/);
  const tab = all(app.ids.content, row => row.dataset.detailTab === 'information')[0]; await tab.click();
  assert.equal(byClass(app.ids.content, 'detail-knowledge')[0].hidden, true);
  assert.deepEqual(app.requests.map(row => row.operation), ['source_detail']);
});

function parchmentFixture() {
  const claim = { claim_key: 'documented', text: '<script>literal W text</script>', epistemic_basis: 'accepted_knowledge',
    k_revision_ids: [REV], effective_edge_revision_ids: [], assumptions: ['Exact user condition'], limitations: ['Historical source limit'] };
  return { schema_version: 'parchment-v1', parchment_id: EXEC, title: 'Canonical topic P', input_wisdom_ids: [OLD],
    body: { sections: [{ wisdom_id: OLD, wisdom_snapshot_sha256: 'b'.repeat(64), wisdom_kind: 'explanation',
      query: 'Explain the selected evidence.', context_snapshot: { condition: 'Frozen context' }, evidence_mode: 'knowledge_only', epistemic_basis: 'accepted_knowledge',
      answer_or_payload: { status: 'insufficient', claims: [claim], recommendation: null, unresolved: ['No cost evidence in selected K'] }, uncertainty: {} }] },
    citations: [{ section_index: 0, wisdom_id: OLD, claims: [{ claim_key: claim.claim_key, k_revision_ids: [REV], effective_edge_refs: [] }] }],
    provenance: { operation: 'w2p', actor: 'test-actor' }, snapshot_sha256: 'c'.repeat(64), created_at: '2026-09-14T13:00:00Z' };
}

test('canonical P joins the Wiki catalog under its source Realm with exact W text and store-qualified K links', async () => {
  const saved = parchmentFixture(), catalog = { kind: 'parchment', parchment_id: EXEC, title: saved.title,
    input_wisdom_ids: [OLD], source_data_ids: [D], store_id: STORE_B };
  const app = ui({ parchment_get: { parchment: saved, source_data_ids: [D], read_only: true },
    knowledge_node: { node: knowledge, evidence: [] } });
  unifiedState(app, { realmId: REALM, realms: [realmFixture({ members: [{ store_id: STORE_B, member_kind: 'data', member_id: D }] })],
    parchments: [catalog], pages: [{ kind: 'paper', page_id: OLD, data_id: D, source_data_ids: [D], title: 'Legacy source document', store_id: STORE_B }] });
  app.run('showWikiIndex()');
  assert.match(app.ids.content.textContent, /Parchment P.*Wisdom 1개 구성/);
  assert.match(app.ids.content.textContent, /기존 I 기반 설명/);
  const card = byClass(app.ids.content, 'wiki-result').find(item => item.textContent.includes(saved.title));
  await card.click();
  assert.deepEqual(app.requests[0], { operation: 'parchment_get', parchment_id: EXEC, store_id: STORE_B });
  assert.match(app.ids.content.textContent, /생성 당시 Wisdom/);
  for (const text of [saved.body.sections[0].answer_or_payload.claims[0].text, 'Exact user condition', 'Historical source limit', 'Frozen context', 'No cost evidence in selected K', OLD]) assert.ok(app.ids.content.textContent.includes(text));
  assert.equal(all(app.ids.content, item => item.tagName === 'SCRIPT').length, 0);
  assert.doesNotMatch(app.ids.content.textContent, /기존 I 기반 설명/);
  await byClass(app.ids.content, 'exact-link')[0].click();
  assert.deepEqual(app.requests.at(-1), { operation: 'knowledge_node', node_revision_id: REV, store_id: STORE_B });
  app.run(`state.realms[0].members=[];showWikiIndex()`);
  assert.equal(byClass(app.ids.content, 'wiki-result').length, 0);
});

test('P in a source-only store shows exact K IDs and ignores a stale document response after navigation', async () => {
  let finish;
  const saved = parchmentFixture();
  const app = ui({ parchment_get: { parchment: saved, source_data_ids: [D], read_only: true },
    knowledge_node: { node: knowledge, evidence: [] } });
  unifiedState(app);
  await app.run(`openParchment('${EXEC}','${STORE_A}')`);
  assert.equal(byClass(app.ids.content, 'exact-link').length, 1);
  assert.match(app.ids.content.textContent, new RegExp(`K Revision ${REV}`));
  await byClass(app.ids.content, 'exact-link')[0].click();
  assert.deepEqual(app.requests.map(row => row.operation), ['parchment_get', 'knowledge_node']);
  const later = ui({ parchment_get: () => new Promise(resolve => { finish = resolve; }) });
  unifiedState(later);
  const pending = later.run(`openParchment('${EXEC}','${STORE_A}')`);
  later.run('showData()'); finish({ parchment: saved, source_data_ids: [D], read_only: true }); await pending;
  assert.equal(byClass(later.ids.content, 'data-card').length, 1);
  assert.doesNotMatch(later.ids.content.textContent, /Canonical topic P/);
});
