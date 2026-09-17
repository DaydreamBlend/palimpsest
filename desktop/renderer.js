import { PdfPanel } from './pdf-view.js';

const $ = (id) => document.getElementById(id);
const state = { mode: 'wiki', filter: 'all', search: '', pages: [], queries: [], knowledge: [], reviews: [], sources: [], versions: [], nodeRevisionId: null, reviewId: null, page: null, queryId: null, pageTicket: 0, sourceTicket: 0, pdfTicket: 0, evidence: null, information: null, sourceTab: 'information', pdfPage: 1, pdfCount: null, pdfOpened: false };
Object.assign(state, { unified: false, stores: [], storeId: null, data: [], dataId: null, dataFilter: 'all', realmId: 'all', realms: [], storeErrors: [], parchments: [] });
state.assignmentTicket = 0;
const labels = { overview: '개요', methods: '연구 방법', findings: '주요 결과', results: '주요 결과', limitations: '한계와 해석', unresolved: '미해결 사항' };
const queryStates = { answered: '답변 검증됨', needs_review: '검토 필요', needs_attention: '확인 필요', needs_source: '원문 확인 대기', needs_information: '추가 근거 필요', invalid_response: '응답 검증 실패', input_ready: '입력 준비됨', prepared: '준비됨' };
let pdfViewer = null;

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}
function button(text, className, action, title) {
  const element = node('button', className, text);
  element.type = 'button';
  if (title) element.title = title;
  element.addEventListener('click', action);
  return element;
}
function append(parent, ...children) { for (const child of children.flat()) if (child) parent.append(child); return parent; }
function short(value, length = 12) { return value ? String(value).slice(0, length) : '알 수 없음'; }
function errorText(error) { return error?.message || '저장된 자료를 불러오지 못했습니다.'; }
function notice(message = '') { $('notice').hidden = !message; $('notice').textContent = message; }
function sourceStatus(message = '') { $('source-status').hidden = !message; $('source-status').textContent = message; }
function request(operation, args = {}, storeId = state.storeId) { return window.palimpsest.request({ operation, ...args, ...(state.unified ? { store_id: storeId } : {}) }); }
function sourcePage(dataId, storeId = state.storeId) { return state.pages.find((p) => p.kind === 'paper' && p.data_id === dataId && (!state.unified || p.store_id === storeId)); }
function sourceName(dataId, storeId = state.storeId) { return sourcePage(dataId, storeId)?.title || state.sources.find((source) => source.data_id === dataId && (!state.unified || source.store_id === storeId))?.title || state.data.find((source) => source.data_id === dataId && source.store_id === storeId)?.filename || `Data ${short(dataId)}`; }
function selectStore(storeId) {
  if (!state.unified || state.storeId === storeId) return;
  if (!state.stores.some(store => store.store_id === storeId)) throw new Error('unknown_desktop_store');
  ++state.pageTicket; closeSource(); state.page = null; state.queryId = null; state.nodeRevisionId = null; state.reviewId = null;
  state.storeId = storeId;
}
function storeLabel(storeId) { return state.stores.find(store => store.store_id === storeId)?.label || ''; }
const formatNames = { pdf: 'PDF', code: '코드', markdown: 'Markdown', web: '웹 문서', text: '텍스트', image: '이미지', other: '기타' };
function inRealm(source) {
  if (state.realmId === 'all') return true;
  const matches = realm => realm.members.some(member => member.store_id === source.store_id &&
    (member.member_kind === 'data' ? member.member_id === source.data_id : (source.versions || []).some(version => version.series_id === member.member_id)));
  return state.realmId === 'unassigned' ? !state.realms.some(matches) : state.realms.some(realm => realm.realm_id === state.realmId && matches(realm));
}
function realmName() { return state.realmId === 'all' ? '모든 Realm' : state.realmId === 'unassigned' ? '미분류 자료' : state.realms.find(realm => realm.realm_id === state.realmId)?.name || 'Realm'; }
function realmNames(source) {
  return state.realms.filter(realm => realm.members.some(member => member.store_id === source.store_id &&
    (member.member_kind === 'data' ? member.member_id === source.data_id : (source.versions || []).some(version => version.series_id === member.member_id)))).map(realm => realm.name);
}
function rowInRealm(row) {
  if (!state.unified || state.realmId === 'all') return true;
  const ids = row.source_data_ids || (row.data_id ? [row.data_id] : []);
  return ids.some(id => { const source = state.data.find(value => value.store_id === row.store_id && value.data_id === id); return source && inRealm(source); });
}
function visibleRows(rows) { return rows.filter(rowInRealm); }
function wikiDocuments() { return [...state.pages, ...state.parchments]; }
function documentId(page) { return page.kind === 'parchment' ? page.parchment_id : page.page_id; }
function openWikiDocument(page) { return page.kind === 'parchment' ? openParchment(page.parchment_id, page.store_id) : openPage(page.page_id, undefined, page.store_id); }
function refreshRealmView() {
  if (state.mode === 'wiki') return showWikiIndex();
  if (state.mode === 'knowledge') return showKnowledge();
  if (state.mode === 'reviews') return showReviews();
  if (state.mode === 'queries') return showQueries();
  return showData();
}
function realmTags(source) {
  const group = node('div', 'realm-tags'), names = realmNames(source);
  for (const name of names.length ? names : ['미분류']) group.append(tag(name, names.length ? 'realm' : 'held'));
  return group;
}
function showWikiIndex() {
  ++state.pageTicket; state.mode = 'wiki'; state.page = null; closeSource(); updateNavigation(); notice();
  setCrumb(realmName(), '위키 문서');
  const fragment = document.createDocumentFragment(), pages = visibleRows(wikiDocuments()).filter(page => (state.filter === 'all' || page.kind === state.filter) && page.title.toLocaleLowerCase().includes(state.search.toLocaleLowerCase()));
  append(fragment, node('span', 'eyebrow', 'WIKI / PARCHMENT VIEW'), node('h1', 'query-list-title', '위키 문서'), node('p', 'query-intro', `${realmName()}의 자료별·주제별 문서를 읽습니다. 위키는 설명을 구성한 문서(P)를 보여주는 공간이며, 개별 K는 지식 화면에서 조회합니다.`), node('p', 'query-intro', 'W를 구성한 P와 I를 근거로 만든 기존 설명 문서를 구분해 표시합니다. 기존 설명의 생성 이력과 인용은 그대로 보존합니다.'));
  for (const page of pages) {
    const card = button('', 'wiki-result query-card', () => openWikiDocument(page));
    append(card, tag(page.kind === 'parchment' ? 'Parchment P' : page.kind === 'topic' ? '주제' : sourceLabel(page)), tag(page.kind === 'parchment' ? `Wisdom ${page.input_wisdom_ids.length}개 구성` : '기존 I 기반 설명'), node('h2', '', page.title), node('p', 'source-image-caption', storeLabel(page.store_id)));
    fragment.append(card);
  }
  if (!pages.length) fragment.append(node('p', 'query-intro', '이 Realm에는 현재 표시할 위키가 없습니다. 원본과 I는 모든 자료에서 확인할 수 있습니다.'));
  $('content').replaceChildren(fragment); $('main').scrollTop = 0;
}
function groupedData() {
  const groups = new Map(), query = state.search.toLocaleLowerCase();
  for (const source of state.data) {
    if (!inRealm(source) || (state.dataFilter !== 'all' && state.dataFilter !== source.source_kind) ||
        !`${source.filename || ''} ${source.data_id}`.toLocaleLowerCase().includes(query)) continue;
    if (!groups.has(source.data_id)) groups.set(source.data_id, { data_id: source.data_id, locations: [] });
    groups.get(source.data_id).locations.push(source);
  }
  return [...groups.values()];
}
function preferredLocation(locations) { return locations.find(source => sourcePage(source.data_id, source.store_id)) || locations[0]; }
function dataTitle(source) {
  const page = sourcePage(source.data_id, source.store_id); if (page) return page.title;
  const version = source.versions?.at(-1);
  if (version?.title) return `${version.title} · v${version.version_number}`;
  const name = source.filename || source.original_name || '등록 자료';
  return state.data.some(other => other.data_id !== source.data_id && other.filename === source.filename) ? `${name} · ${short(source.data_id, 8)}` : name;
}
async function acrossStores(operation, fields, capability = 'hasWiki') {
  const result = Object.fromEntries(fields.map(field => [field, []]));
  const stores = state.stores.filter(store => store.connected && (!capability || store[capability]));
  const responses = await Promise.allSettled(stores.map(store => request(operation, {}, store.store_id)));
  responses.forEach((response, index) => {
    const store = stores[index];
    if (response.status === 'fulfilled') {
      for (const field of fields) result[field].push(...(response.value[field] || []).map(row => ({ ...row, store_id: store.store_id })));
      if (response.value.issues?.length) state.storeErrors.push(`${store.label} · ${response.value.issues.length}개 기록의 무결성 확인 필요`);
    } else state.storeErrors.push(`${store.label} · ${errorText(response.reason)}`);
  });
  return result;
}
function showData() {
  ++state.pageTicket; state.mode = 'data'; state.dataId = null; closeSource(); updateNavigation();
  setCrumb('자료', state.realmId === 'all' ? '모든 Realm' : state.realms.find(realm => realm.realm_id === state.realmId)?.name || '미분류');
  const fragment = document.createDocumentFragment(), groups = groupedData();
  append(fragment, node('span', 'eyebrow', 'LIBRARY / KNOWLEDGE WITH SOURCES'), node('h1', 'query-list-title', '모든 자료'),
    node('p', 'query-intro', `${realmName()}의 원본에서 지식과 근거를 찾아보세요.`));
  const stats = node('div', 'stats-row');
  for (const [label, number] of [['원본 D', groups.length], ['위키 문서', visibleRows(wikiDocuments()).length], ['Realm', state.realms.length]]) append(stats, append(node('div', 'stat-box'), node('span', '', label), node('strong', '', number)));
  fragment.append(stats);
  for (const group of groups) {
    const source = preferredLocation(group.locations), wiki = sourcePage(source.data_id, source.store_id);
    const card = node('article', 'data-card'), body = node('div', 'data-card-body');
    append(card, node('span', 'type-badge D', 'D'), body);
    append(body, append(node('div', 'knowledge-flags'), tag(formatNames[source.source_kind] || source.source_kind), tag(wiki ? 'Wiki 있음' : '등록 자료'),
      ...(group.locations.length > 1 ? [tag(`${group.locations.length}개 보존 위치`)] : [])),
      button(dataTitle(source), 'data-title', () => openData(source.store_id, source.data_id)),
      node('p', 'review-reason', `보존 이력 전체 ${source.information_count}개 I · ${source.source_execution_count}개 D2I 실행 · ${source.byte_size.toLocaleString()} bytes`));
    body.append(realmTags(source));
    const actions = node('div', 'button-row');
    if (wiki) actions.append(button('Wiki 읽기 →', 'exact-link', () => openPage(wiki.page_id, undefined, source.store_id)));
    actions.append(button('Realm 지정', 'assign-realm-button', () => openAssignment(source)));
    body.append(actions);
    fragment.append(card);
  }
  if (!groups.length) fragment.append(node('p', 'query-intro', '현재 선택한 범위에 등록 자료가 없습니다.'));
  $('content').replaceChildren(fragment); notice(state.storeErrors.join(' / '));
}
async function openData(storeId, dataId) {
  selectStore(storeId); const ticket = ++state.pageTicket;
  state.mode = 'data'; state.dataId = dataId; closeSource(); notice(); updateNavigation(); loading('등록 자료를 여는 중입니다');
  try {
    const result = await request('source_detail', { data_id: dataId }, storeId);
    if (ticket !== state.pageTicket) return;
    const source = result.data, fragment = document.createDocumentFragment(), wiki = sourcePage(dataId, storeId);
    setCrumb('자료', formatNames[source.source_kind] || '등록 원본');
    append(fragment, button('‹ 모든 자료', 'back-button', showData), node('div', 'eyebrow', 'REGISTERED DATA'),
      node('h1', 'document-title', dataTitle({ ...source, store_id: storeId })),
      append(node('div', 'document-meta'), tag(formatNames[source.source_kind] || source.source_kind), node('span', '', storeLabel(storeId)), tag(`${source.byte_size.toLocaleString()} bytes`)));
    if (wiki) fragment.append(button('이 자료의 Wiki 읽기 →', 'exact-link', () => openPage(wiki.page_id, undefined, storeId)));
    append(fragment, realmTags({ ...source, store_id: storeId }), button('Realm 지정', 'assign-realm-button', () => openAssignment({ ...source, store_id: storeId })));
    fragment.append(button('등록된 원본 D 열기', 'exact-link', () => openOriginalData(storeId, source)));
    const locations = state.data.filter(row => row.data_id === dataId && row.store_id !== storeId);
    if (locations.length) {
      const other = details('같은 원본의 다른 보존 위치');
      other.append(node('p', '', '원본 SHA-256은 같지만, 선택한 위치의 I·K와 실행 이력을 각각 표시합니다.'));
      for (const location of locations) other.append(button(`${storeLabel(location.store_id)} · ${location.information_count}개 I`, 'exact-link', () => openData(location.store_id, dataId)));
      fragment.append(other);
    }
    if (result.versions?.length) { const versions = details(`자료 버전 · ${result.versions.length}`); versions.append(versionList(result.versions)); fragment.append(versions); }
    const section = node('section', 'review-block'); section.append(node('h2', '', `Information · ${result.information.length}`));
    for (const execution of [...result.executions].reverse()) {
      const units = result.information.filter(unit => unit.source_execution_id === execution.execution_id);
      const group = details(`${reviewState(execution.state)} · ${units.length}개 I · ${short(execution.execution_id)}`, 'review-item');
      group.append(node('code', 'revision-id', `D2I ${execution.execution_id} · ${execution.profile?.transformation?.algorithm || execution.profile_id}`));
      if (execution.error_code) group.append(node('p', 'failure-note', execution.error_code));
      for (const unit of units) group.append(button(`${unit.title || unit.unit_type || unit.kind} · ${unit.character_count}자`, 'source-information-link', () => openEvidence({
        ...unit, sourceOnly: true, store_id: storeId, page_numbers: [...new Set((unit.source_refs || []).map(ref => ref.page_number || (Number.isInteger(ref.page_index) ? ref.page_index + 1 : null)).filter(Boolean))]
      })));
      section.append(group);
    }
    if (!result.executions.length) section.append(node('p', 'review-reason', 'D는 등록되어 있으며, 아직 D2I 실행 기록이 없습니다.'));
    const knowledge = node('section', 'detail-knowledge'); knowledge.append(node('h2', '', `지식 K · ${result.knowledge.length}`));
    if (!result.knowledge.length) knowledge.append(node('p', 'review-reason', '이 원본에 연결된 K는 아직 없습니다. I와 I2K 실행 상태를 아래에서 확인할 수 있습니다.'));
    for (const entry of result.knowledge) {
      const card = node('div', 'knowledge-card'); append(card, knowledgeFlags(entry), node('p', '', entry.statement), node('code', 'revision-id', entry.knode_revision_id));
      card.append(button('지식과 생성 근거 열기', 'exact-link', () => openKnowledge(entry.knode_revision_id, storeId)));
      for (const grounding of entry.groundings || []) card.append(button(`근거 I ${short(grounding.information_id)}`, 'evidence-link', () => openEvidence({ ...grounding, sourceOnly: true, store_id: storeId })));
      knowledge.append(card);
    }
    const progress = node('section', 'compilation-status');
    const runs = result.i2k_executions || [], calls = runs.reduce((sum, run) => sum + run.successful_model_calls, 0);
    const complete = runs.some(run => run.state === 'completed');
    append(progress, tag(!calls ? 'I2K 모델 미실행' : complete ? '완료된 I2K 있음' : 'I2K 검토 진행'), node('span', '', `보존 KRevision ${result.knowledge.length}개 · I2K 실행 이력 ${runs.length}개 · 성공한 모델 호출 ${calls}회`));
    const log = details('I2K 실행 상태와 검토 이력');
    for (const run of runs) append(log, append(node('div', 'version-row'), tag(reviewState(run.state), run.state === 'completed' ? 'accepted' : 'held'), node('span', '', `모델 ${run.successful_model_calls}회 · 새/개정 K ${run.created_or_revised_nodes} · 재사용 ${run.reused_records}`), node('code', '', run.execution_id)));
    if (!runs.length) log.append(node('p', 'review-reason', '아직 I2K 실행 기록이 없습니다.'));
    progress.append(log); fragment.append(progress);
    const tabs = node('div', 'detail-tabs');
    const panels = [['knowledge', `지식 K · ${result.knowledge.length}`, knowledge], ['information', `정보 I · ${result.information.length}`, section]];
    const selected = result.knowledge.length ? 'knowledge' : 'information';
    for (const [key, label, panel] of panels) {
      panel.hidden = key !== selected;
      const tab = button(label, key === selected ? 'active' : '', () => {
        for (const [other, , target] of panels) target.hidden = other !== key;
        for (const item of tabs.children) { const active = item.dataset.detailTab === key; item.classList.toggle('active', active); item.setAttribute('aria-selected', String(active)); }
      });
      tab.dataset.detailTab = key; tab.setAttribute('role', 'tab'); tab.setAttribute('aria-selected', String(key === selected)); tabs.append(tab);
    }
    tabs.setAttribute('role', 'tablist'); tabs.setAttribute('aria-label', '자료의 지식과 정보');
    append(fragment, tabs, knowledge, section);
    const provenance = details('원본 식별과 등록 이력'); provenance.append(keyValues([['Data · SHA-256', dataId], ['보존 위치', storeLabel(storeId)], ['MIME', source.media_type]]));
    for (const acquisition of result.acquisitions || []) provenance.append(keyValues([['등록 이름', acquisition.original_name], ['등록 시각', acquisition.created_at], ['등록 경로', acquisition.origin_uri]]));
    fragment.append(provenance); $('content').replaceChildren(fragment); $('main').scrollTop = 0;
  } catch (error) { if (ticket === state.pageTicket) empty('자료를 열지 못했습니다', errorText(error), () => openData(storeId, dataId)); }
}
async function openOriginalData(storeId, source) {
  if (source.media_type === 'application/pdf') return openEvidence({ data_id: source.data_id, sourceOnly: true, store_id: storeId, page_number: 1 });
  closeSource(); const ticket = ++state.sourceTicket; $('source-panel').hidden = false;
  $('source-label').textContent = source.filename; $('pdf-tab').hidden = true; selectSourceTab('information', false);
  sourceStatus('등록 원본 bytes를 검증하는 중입니다.');
  try {
    const original = await request('source_artifact', { data_id: source.data_id }, storeId);
    if (ticket !== state.sourceTicket) return;
    const body = node('div');
    append(body, keyValues([['원본 SHA-256', original.sha256], ['형식', original.media_type], ['Bytes', original.byte_size]]));
    if (typeof original.text === 'string') body.append(node('pre', 'information-text code-text', original.text));
    else if (['image/png', 'image/jpeg', 'image/webp'].includes(original.media_type)) { const picture = node('img', 'source-image'); picture.src = `data:${original.media_type};base64,${original.base64}`; picture.alt = source.filename; body.append(picture); }
    else body.append(node('p', 'review-reason', '원본의 정확한 bytes를 확인했습니다. 이 파일 형식의 미리 보기는 아직 지원하지 않습니다.'));
    $('information-view').replaceChildren(body); sourceStatus();
  } catch (error) { if (ticket === state.sourceTicket) sourceStatus(errorText(error)); }
}
async function bootUnified(reconnect) {
  $('reconnect').disabled = true; const ticket = ++state.pageTicket;
  closeSource(); $('connection-label').textContent = '자료 공간 연결 중';
  try {
    const stores = await window.palimpsest.stores();
    await Promise.allSettled(stores.filter(store => reconnect || !store.connected).map(store => window.palimpsest.reconnect(store.store_id)));
    if (ticket !== state.pageTicket) return;
    state.unified = true; state.stores = await window.palimpsest.stores(); state.storeErrors = [];
    state.storeId = state.stores.find(store => store.store_id === state.storeId)?.store_id || state.stores[0]?.store_id;
    for (const store of state.stores) if (!store.connected) state.storeErrors.push(`${store.label} · ${store.error || '연결 확인 필요'}`);
    const [sources, pages, queries, parchments] = await Promise.all([
      acrossStores('source_catalog', ['data'], null), acrossStores('catalog', ['pages']), acrossStores('queries', ['queries'], 'hasQueries'), acrossStores('parchment_catalog', ['parchments'], null)]);
    if (ticket !== state.pageTicket) return;
    state.data = sources.data; state.pages = pages.pages; state.queries = queries.queries;
    state.parchments = parchments.parchments.map(page => ({ ...page, kind: 'parchment' }));
    const connected = state.stores.filter(store => store.connected).length;
    $('connection-label').textContent = `${connected}/${state.stores.length}개 저장소 연결`;
    $('connection-dot').className = `status-dot ${connected ? 'connected' : 'failed'}`;
    if (typeof window.palimpsest.realms === 'function') {
      try { const result = await window.palimpsest.realms({ operation: 'catalog' }); if (ticket !== state.pageTicket) return; state.realms = result.realms; }
      catch (error) { if (ticket !== state.pageTicket) return; state.storeErrors.push(`Realm · ${errorText(error)}`); }
    }
    if (ticket !== state.pageTicket) return;
    updateRealmOptions(); showData();
  } catch (error) { if (ticket === state.pageTicket) empty('자료 공간에 연결하지 못했습니다', errorText(error), () => boot(true)); }
  finally { $('reconnect').disabled = false; }
}
function updateRealmOptions() {
  const select = $('realm-select'); if (!select) return;
  const options = [['all', '모든 Realm'], ['unassigned', '미분류 자료'], ...state.realms.map(realm => [realm.realm_id, realm.name])];
  if (!options.some(([value]) => value === state.realmId)) state.realmId = 'all';
  select.replaceChildren(...options.map(([value, text]) => { const option = node('option', '', text); option.value = value; option.selected = value === state.realmId; return option; }));
}
function newRequestId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  let time = Date.now(); for (let index = 5; index >= 0; index--) { bytes[index] = time % 256; time = Math.floor(time / 256); }
  bytes[6] = (bytes[6] & 15) | 112; bytes[8] = (bytes[8] & 63) | 128;
  const hex = [...bytes].map(value => value.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
function realmMemberKey(member) { return `${member.store_id}/${member.member_kind}/${member.member_id}`; }
function closeAssignment() {
  ++state.assignmentTicket;
  const dialog = $('realm-assignment');
  if (typeof dialog.close === 'function') dialog.close();
  dialog.hidden = true;
}
function assignmentMembers(source, scope) {
  if (scope === 'data') return state.data.filter(row => row.data_id === source.data_id).map(row => ({ store_id: row.store_id, member_kind: 'data', member_id: row.data_id }));
  const version = (source.versions || []).find(version => version.series_id === scope);
  if (!version) throw new Error('invalid_assignment_series');
  return [{ store_id: source.store_id, member_kind: 'data_series', member_id: version.series_id }];
}
async function openAssignment(source) {
  const ticket = ++state.assignmentTicket, dialog = $('realm-assignment');
  $('assignment-title').textContent = dataTitle(source);
  $('assignment-body').replaceChildren(node('p', 'review-reason', '현재 Realm 소속을 확인하고 있습니다.'));
  dialog.hidden = false; if (typeof dialog.showModal === 'function' && !dialog.open) dialog.showModal();
  try {
    const result = await window.palimpsest.realms({ operation: 'catalog' });
    if (ticket !== state.assignmentTicket) return;
    state.realms = result.realms; updateRealmOptions();
    renderAssignment(source, ticket);
  } catch (error) { if (ticket === state.assignmentTicket) $('assignment-body').replaceChildren(node('p', 'review-notice', errorText(error))); }
}
function renderAssignment(source, ticket, selection = {}) {
  const body = $('assignment-body'), fragment = document.createDocumentFragment();
  append(fragment, node('p', 'review-reason', '자료는 여러 Realm에 속할 수 있습니다. 각 소속을 개별적으로 추가·해제하며, 같은 원본의 보존 위치는 함께 분류합니다.'), realmTags(source));
  if (!state.realms.length) {
    append(fragment, node('p', 'review-reason', '먼저 Realm을 하나 만들어 주세요.'), button('Realm 만들기', 'realm-save', () => { closeAssignment(); showRealmManager(); }));
    body.replaceChildren(fragment); return;
  }
  const realmSelect = node('select', 'assignment-realm realm-input'); realmSelect.setAttribute('aria-label', '지정할 Realm');
  for (const realm of state.realms) { const option = node('option', '', realm.name); option.value = realm.realm_id; realmSelect.append(option); }
  realmSelect.value = selection.realmId || (state.realms.some(realm => realm.realm_id === state.realmId) ? state.realmId : state.realms[0].realm_id);
  const scope = node('select', 'assignment-scope realm-input'); scope.setAttribute('aria-label', '소속을 적용할 자료 범위');
  const single = node('option', '', `이 원본 D · 보존 위치 ${state.data.filter(row => row.data_id === source.data_id).length}곳`); single.value = 'data'; scope.append(single); scope.value = 'data';
  const seen = new Set();
  for (const version of source.versions || []) if (!seen.has(version.series_id)) {
    seen.add(version.series_id); const option = node('option', '', `자료 계열 전체 · ${version.series_name}`); option.value = version.series_id; scope.append(option);
  }
  if (selection.scope) scope.value = selection.scope;
  const reason = node('input', 'assignment-reason realm-input'); reason.value = selection.reason || '자료 소속 직접 지정'; reason.setAttribute('aria-label', 'Realm 변경 이유');
  const status = node('p', 'assignment-status review-reason'); status.setAttribute('role', 'status');
  let previousPayload, requestId;
  const save = async remove => {
    const realm = state.realms.find(row => row.realm_id === realmSelect.value);
    const selected = assignmentMembers(source, scope.value), keys = new Set(selected.map(realmMemberKey));
    const members = realm.members.filter(member => !keys.has(realmMemberKey(member)));
    if (!remove) members.push(...selected);
    const payload = { operation: 'revise', realm_id: realm.realm_id, expected_revision_id: realm.revision_id,
      name: realm.name, description: realm.description, members, actor: 'desktop-user', reason: reason.value };
    if (!payload.reason.trim()) { status.textContent = '변경 이유를 입력해 주세요.'; return; }
    const encoded = JSON.stringify(payload); if (encoded !== previousPayload) { previousPayload = encoded; requestId = newRequestId(); }
    add.disabled = subtract.disabled = realmSelect.disabled = scope.disabled = true;
    status.textContent = '선택한 Realm의 소속을 저장하고 있습니다.';
    try {
      const saved = await window.palimpsest.realms({ ...payload, request_id: requestId });
      if (ticket !== state.assignmentTicket) return;
      state.realms = state.realms.map(row => row.realm_id === saved.realm_id ? saved : row); updateRealmOptions();
      renderAssignment(source, ticket, { realmId: realmSelect.value, scope: scope.value, reason: reason.value }); notice(`“${saved.name}” Realm 소속을 저장했습니다.`);
      if (state.mode === 'data' && state.dataId === source.data_id) await openData(source.store_id, source.data_id);
      else if (state.mode === 'data' && !state.dataId) showData(); else renderLibrary();
    } catch (error) { if (ticket === state.assignmentTicket) status.textContent = `${errorText(error)} · 다른 곳에서 Realm이 변경됐다면 이 창을 다시 열어 확인하세요.`; }
    finally { if (ticket === state.assignmentTicket) { realmSelect.disabled = scope.disabled = false; add.disabled = subtract.disabled = false; } }
  };
  const add = button('선택 Realm에 지정', 'realm-save', () => save(false));
  const subtract = button('이 범위의 소속 해제', 'realm-remove', () => save(true));
  const describe = () => {
    const realm = state.realms.find(row => row.realm_id === realmSelect.value), selected = assignmentMembers(source, scope.value);
    const keys = new Set(realm.members.map(realmMemberKey)), present = selected.filter(member => keys.has(realmMemberKey(member))).length;
    add.disabled = present === selected.length; subtract.disabled = present === 0;
    const inherited = scope.value === 'data' && realm.members.some(member => member.store_id === source.store_id && member.member_kind === 'data_series' && (source.versions || []).some(version => version.series_id === member.member_id));
    status.textContent = `${realm.name} · 직접 소속 ${present}/${selected.length}개${inherited ? ' · 자료 계열을 통해서도 소속되어 있습니다. 계열 소속을 바꾸려면 적용 범위를 자료 계열 전체로 선택하세요.' : ''}`;
  };
  realmSelect.addEventListener('change', describe); scope.addEventListener('change', describe);
  for (const [label, control] of [['지정할 Realm', realmSelect], ['적용 범위', scope], ['변경 이유', reason]]) { const field = node('label', 'assignment-field'); append(field, node('span', '', label), control); fragment.append(field); }
  append(fragment, status, append(node('div', 'button-row'), add, subtract));
  body.replaceChildren(fragment); describe();
}
async function showRealmManager() {
  const ticket = ++state.pageTicket; closeSource(); state.mode = 'data'; updateNavigation();
  if (typeof window.palimpsest.realms !== 'function') { notice('Realm 연결이 설정되지 않았습니다.'); return; }
  loading('Realm을 읽는 중입니다');
  try {
    const result = await window.palimpsest.realms({ operation: 'catalog' });
    if (ticket !== state.pageTicket) return;
    state.realms = result.realms; updateRealmOptions(); setCrumb('자료', 'Realm 관리');
    const fragment = document.createDocumentFragment(), choices = node('select', 'realm-picker'), editor = node('div');
    choices.setAttribute('aria-label', '수정할 Realm 선택');
    for (const realm of [{ realm_id: '', name: '새 Realm 만들기' }, ...state.realms]) { const option = node('option', '', realm.name); option.value = realm.realm_id; choices.append(option); }
    append(fragment, button('‹ 모든 자료', 'back-button', showData), node('h1', 'query-list-title', 'Realm'),
      node('p', 'query-intro', '함께 다룰 자료를 주제나 프로젝트별로 묶습니다. 자료는 여러 Realm에 속할 수 있습니다. I2K는 같은 Realm을 기본으로 사용하며 교차 결합에는 명시적인 선택이 필요합니다.'), choices, editor);
    choices.addEventListener('change', () => renderRealmEditor(editor, state.realms.find(realm => realm.realm_id === choices.value), ++state.pageTicket));
    $('content').replaceChildren(fragment); renderRealmEditor(editor, undefined, ticket);
  } catch (error) { if (ticket === state.pageTicket) empty('Realm을 읽지 못했습니다', errorText(error), showRealmManager); }
}
function renderRealmEditor(container, realm, ticket) {
  const fragment = document.createDocumentFragment(), fields = {};
  for (const [key, label, value] of [['name', 'Realm 이름', realm?.name || ''], ['description', '설명', realm?.description || ''], ['reason', '변경 이유', '']]) {
    const field = node(key === 'description' ? 'textarea' : 'input', 'realm-input'); field.value = value; field.id = `realm-${key}`; fields[key] = field;
    const title = node('label', 'realm-field', label); title.setAttribute('for', field.id); append(fragment, title, field);
  }
  const selected = new Set((realm?.members || []).map(realmMemberKey)), choices = new Map();
  for (const source of state.data) {
    const members = [{ member: { store_id: source.store_id, member_kind: 'data', member_id: source.data_id }, label: `${dataTitle(source)} · ${short(source.data_id, 8)}` },
      ...(source.versions || []).map(version => ({ member: { store_id: source.store_id, member_kind: 'data_series', member_id: version.series_id }, label: `${version.series_name || '자료 계열'} · 모든 버전` }))];
    for (const item of members) choices.set(realmMemberKey(item.member), { ...item, label: `${item.label} · ${storeLabel(source.store_id)}` });
  }
  for (const member of realm?.members || []) if (!choices.has(realmMemberKey(member))) choices.set(realmMemberKey(member), { member, label: `현재 확인할 수 없는 보존 참조 · ${member.member_id}` });
  if (realm) {
    fragment.append(node('p', 'review-reason', '자료 계열을 선택하면 이후 버전도 이 Realm에 속합니다. 실행 시에는 정확한 자료 버전을 별도로 고정합니다.'));
    const list = node('div', 'realm-members');
    for (const [key, choice] of choices) {
      const row = node('label', 'realm-member'), checkbox = node('input'); checkbox.type = 'checkbox'; checkbox.checked = selected.has(key);
      checkbox.addEventListener('change', () => { if (checkbox.checked) selected.add(key); else selected.delete(key); });
      append(row, checkbox, node('span', '', choice.label)); list.append(row);
    }
    fragment.append(list);
  } else fragment.append(node('p', 'review-reason', 'Realm을 만든 다음 자료를 선택해 추가할 수 있습니다.'));
  const status = node('p', 'review-reason'); status.setAttribute('role', 'status'); let previousPayload, requestId;
  const save = button(realm ? '변경 저장' : 'Realm 만들기', 'realm-save', async () => {
    const payload = { operation: realm ? 'revise' : 'create', name: fields.name.value, description: fields.description.value, actor: 'desktop-user', reason: fields.reason.value,
      ...(realm ? { realm_id: realm.realm_id, expected_revision_id: realm.revision_id, members: [...selected].map(key => choices.get(key).member) } : {}) };
    if (!payload.name.trim() || !payload.reason.trim()) { status.textContent = '이름과 변경 이유를 입력하세요.'; return; }
    const encoded = JSON.stringify(payload); if (encoded !== previousPayload) { previousPayload = encoded; requestId = newRequestId(); }
    save.disabled = true; status.textContent = '저장하는 중입니다.';
    try {
      const saved = await window.palimpsest.realms({ ...payload, request_id: requestId });
      if (ticket !== state.pageTicket) return;
      state.realms = [...state.realms.filter(item => item.realm_id !== saved.realm_id), saved]; updateRealmOptions();
      renderRealmEditor(container, saved, ticket); notice(`“${saved.name}”의 Realm Revision ${saved.revision_no}을 저장했습니다.`);
    } catch (error) { if (ticket === state.pageTicket) status.textContent = `${errorText(error)} · 현재 Realm이 변경된 경우 관리 화면을 다시 열어 확인하세요.`; }
    finally { save.disabled = false; }
  });
  append(fragment, save, status);
  if (realm) {
    const history = details(`Realm Revision ${realm.revision_no} · 변경 이력`);
    history.append(button('보존된 이력 읽기', 'exact-link', async () => {
      try {
        const result = await window.palimpsest.realms({ operation: 'history', realm_id: realm.realm_id });
        if (ticket !== state.pageTicket) return;
        history.replaceChildren(node('summary', '', '보존된 Realm 변경 이력'));
        for (const revision of result.revisions) append(history, node('p', 'review-reason', `Revision ${revision.revision_no} · ${revision.name} · ${revision.members.length}개 참조 · ${revision.reason}`), node('code', 'revision-id', revision.revision_id));
      } catch (error) { if (ticket === state.pageTicket) status.textContent = errorText(error); }
    })); fragment.append(history);
  }
  container.replaceChildren(fragment);
}
function sourceFormat(page) { const storeId = page.store_id || state.storeId; return page.source_format || sourcePage(page.data_id, storeId)?.source_format || state.sources.find(source => source.data_id === page.data_id && (!state.unified || source.store_id === storeId))?.source_format; }
function sourceLabel(page) { return sourceFormat(page) === 'code' ? '코드' : sourceFormat(page) === 'pdf' ? '논문' : '자료'; }
function setCrumb(mode, title) { $('breadcrumb').replaceChildren(document.createTextNode(mode), node('span', '', '/'), document.createTextNode(title)); }
function tag(text, kind = '') { return node('span', `tag ${kind}`, text); }
function details(title, className = 'details-panel') { const element = node('details', className); element.append(node('summary', '', title)); return element; }
function keyValues(entries) {
  const list = node('dl', 'key-value');
  for (const [key, value] of entries) append(list, node('dt', '', key), node('dd', '', value ?? '알 수 없음'));
  return list;
}
function empty(title, message, retry) {
  const element = node('div', 'empty-state');
  append(element, node('h1', '', title), node('p', '', message));
  if (retry) element.append(button('다시 시도', '', retry));
  $('content').replaceChildren(element);
}
function loading(title) {
  const element = node('div', 'empty-state');
  append(element, node('div', 'loading-ring'), node('h1', '', title), node('p', '', '저장된 자료와 근거 연결을 읽고 있습니다.'));
  $('content').replaceChildren(element);
}
function updateNavigation() {
  for (const mode of ['data', 'wiki', 'queries', 'knowledge', 'reviews']) {
    const element = $(`${mode}-nav`);
    if (!element) continue;
    element.classList.toggle('active', state.mode === mode);
    if (state.mode === mode) element.setAttribute('aria-current', 'page'); else element.removeAttribute('aria-current');
  }
  $('wiki-count').textContent = visibleRows(wikiDocuments()).length || '';
  $('query-count').textContent = visibleRows(state.queries).length || '';
  $('knowledge-count').textContent = visibleRows(state.knowledge).length || '';
  $('review-count').textContent = visibleRows(state.reviews).length || '';
  const dataCount = new Set(state.data.filter(inRealm).map(value => value.data_id)).size;
  if ($('data-count')) $('data-count').textContent = dataCount || '';
  const navigation = { data: ['모든 자료', dataCount, '자료 이름 검색'], wiki: ['라이브러리', visibleRows(wikiDocuments()).length, '문서 제목 검색'], queries: ['저장된 질문', visibleRows(state.queries).length, '질문 검색'], knowledge: ['지식과 근거', visibleRows(state.knowledge).length, '지식 내용 검색'], reviews: ['원문 검토 기록', visibleRows(state.reviews).length, '자료·검토 상태 검색'] }[state.mode];
  $('library-label').textContent = navigation[0];
  $('library-count').textContent = `${navigation[1]} RECORDS`;
  $('filters').hidden = state.mode !== 'wiki';
  if ($('data-filters')) $('data-filters').hidden = state.mode !== 'data';
  if ($('realm-controls')) $('realm-controls').hidden = !state.unified;
  $('active-realm').textContent = state.unified ? realmName() : '로컬 자료';
  if ($('data-nav')) $('data-nav').hidden = !state.unified;
  $('search').placeholder = navigation[2];
  $('search').setAttribute('aria-label', $('search').placeholder);
  renderLibrary();
}
function renderLibrary() {
  const fragment = document.createDocumentFragment();
  const query = state.search.toLocaleLowerCase();
  const pages = visibleRows(wikiDocuments()).filter((p) => (state.filter === 'all' || p.kind === state.filter) && p.title.toLocaleLowerCase().includes(query));
  if (state.mode === 'data') {
    for (const group of groupedData()) {
      const source = preferredLocation(group.locations);
      const item = button('', `page-link ${state.dataId === source.data_id ? 'active' : ''}`, () => openData(source.store_id, source.data_id));
      append(item, node('span', 'page-icon', source.source_kind === 'code' ? '⌘' : '▧'), node('span', 'page-link-title', dataTitle(source)));
      fragment.append(item);
    }
    if (!fragment.childNodes.length) fragment.append(node('p', 'sidebar-message', '이 범위에 표시할 등록 자료가 없습니다.'));
  } else if (state.mode === 'wiki') {
    for (const kind of ['parchment', 'paper', 'topic']) {
      const group = pages.filter((p) => p.kind === kind);
      if (!group.length) continue;
      fragment.append(node('div', 'library-group', `${kind === 'parchment' ? 'Parchment P' : kind === 'paper' ? '기존 자료 설명' : '기존 주제 설명'} · ${group.length}`));
      for (const page of group) {
        const selected = state.page?.kind === page.kind && documentId(state.page) === documentId(page) && (!state.unified || state.storeId === page.store_id);
        const item = button('', `page-link ${selected ? 'active' : ''}`, () => openWikiDocument(page), page.title);
        append(item, node('span', 'page-icon', kind === 'paper' ? (sourceFormat(page) === 'code' ? '⌘' : '▧') : '·'), node('span', 'page-link-title', page.title));
        if (selected) item.setAttribute('aria-current', 'page');
        fragment.append(item);
      }
    }
    if (!pages.length) fragment.append(node('p', 'sidebar-message', wikiDocuments().length ? '검색 결과가 없습니다.' : '아직 표시할 문서가 없습니다.'));
  } else if (state.mode === 'queries') {
    const queries = visibleRows(state.queries).filter((q) => q.question.toLocaleLowerCase().includes(query));
    for (const query of queries) {
      const item = button('', `page-link query-link ${state.queryId === query.query_id && (!state.unified || state.storeId === query.store_id) ? 'active' : ''}`, () => openQuery(query.query_id, query.store_id), query.question);
      append(item, node('span', 'page-icon', query.state === 'answered' ? '✓' : '◷'), node('span', 'page-link-title', query.question));
      fragment.append(item);
    }
    if (!queries.length) fragment.append(node('p', 'sidebar-message', '표시할 질문 기록이 없습니다.'));
  } else {
    const knowledge = state.mode === 'knowledge';
    const rows = visibleRows(knowledge ? state.knowledge : state.reviews).filter((row) => (knowledge ? row.statement : `${sourceName(row.data_id, row.store_id)} ${reviewState(row.state)}`).toLocaleLowerCase().includes(query));
    for (const row of rows) {
      const id = knowledge ? row.knode_revision_id : row.execution_id;
      const title = knowledge ? row.statement : `${sourceName(row.data_id, row.store_id)} · ${reviewState(row.state)}`;
      const selected = id === (knowledge ? state.nodeRevisionId : state.reviewId) && (!state.unified || state.storeId === row.store_id);
      const item = button('', `page-link ${selected ? 'active' : ''}`, () => knowledge ? openKnowledge(id, row.store_id) : openReview(id, row.store_id), title);
      append(item, node('span', 'page-icon', knowledge ? '◇' : '◉'), node('span', 'page-link-title', title));
      if (selected) item.setAttribute('aria-current', 'page');
      fragment.append(item);
    }
    if (!rows.length) fragment.append(node('p', 'sidebar-message', '표시할 기록이 없습니다.'));
  }
  $('library').replaceChildren(fragment);
}
function historySelect(data) {
  const select = node('select', 'history-select');
  select.setAttribute('aria-label', '문서 snapshot 선택');
  for (const [index, item] of (data.history || []).entries()) {
    const option = node('option', '', `${item.snapshot_id === data.current_snapshot_id ? '현재 문서' : `이전 문서 ${index}`} · ${short(item.snapshot_id, 8)}`);
    option.value = item.snapshot_id;
    option.selected = item.snapshot_id === data.page.snapshot_id;
    select.append(option);
  }
  select.addEventListener('change', () => openPage(data.page.page_id, select.value));
  return select;
}
async function openPage(pageId, snapshotId, storeId = state.storeId) {
  selectStore(storeId);
  const ticket = ++state.pageTicket;
  state.mode = 'wiki'; state.queryId = null;
  closeSource(); notice(); updateNavigation();
  loading('문서를 여는 중입니다');
  try {
    const data = await request('page', { page_id: pageId, ...(snapshotId ? { snapshot_id: snapshotId } : {}) });
    if (ticket !== state.pageTicket) return;
    state.page = { ...data.page, ...(state.unified ? { store_id: storeId } : {}) };
    renderPage(data); updateNavigation(); $('main').scrollTop = 0;
  } catch (error) {
    if (ticket !== state.pageTicket) return;
    empty('문서를 열지 못했습니다', errorText(error), () => openPage(pageId, snapshotId));
  }
}
async function openParchment(parchmentId, storeId = state.storeId) {
  selectStore(storeId); const ticket = ++state.pageTicket;
  state.mode = 'wiki'; state.page = null; state.queryId = null;
  closeSource(); notice(); updateNavigation(); loading('Parchment와 정확한 Wisdom을 읽는 중입니다');
  try {
    const data = await request('parchment_get', { parchment_id: parchmentId }, storeId);
    if (ticket !== state.pageTicket) return;
    state.page = { kind: 'parchment', parchment_id: parchmentId, title: data.parchment.title, store_id: storeId };
    renderParchment(data.parchment, storeId); updateNavigation(); $('main').scrollTop = 0;
  } catch (error) { if (ticket === state.pageTicket) empty('Parchment를 열지 못했습니다', errorText(error), () => openParchment(parchmentId, storeId)); }
}
function renderParchment(parchment, storeId = state.storeId) {
  setCrumb('위키 문서', 'Parchment P');
  const fragment = document.createDocumentFragment();
  append(fragment, append(node('div', 'document-topline'), button('‹ 위키 문서', 'back-button', showWikiIndex),
    node('span', 'eyebrow', 'PARCHMENT / EXACT WISDOM')), node('h1', 'document-title', parchment.title),
    append(node('div', 'document-meta'), tag('Parchment P'), tag(`Wisdom ${parchment.input_wisdom_ids.length}개 구성`)),
    node('p', 'query-intro', '생성 당시 Wisdom의 설명·추천과 근거를 보존한 문서입니다. 현재 K 상태는 개별 Revision에서 확인합니다.'));
  const article = node('article', 'article-paper');
  for (const [index, section] of parchment.body.sections.entries()) {
    const block = node('section', 'article-section');
    append(block, node('h2', '', section.query), tag(section.wisdom_kind === 'recommendation' ? '추천 W · 조언' : '설명 W'), node('code', 'revision-id', `Wisdom ${section.wisdom_id}`));
    const context = details('당시 질문의 조건');
    context.append(node('pre', 'evidence-quote', JSON.stringify(section.context_snapshot, null, 2))); block.append(context);
    for (const claim of section.answer_or_payload.claims) {
      const item = node('div', 'article-item'); item.dataset.claimKey = claim.claim_key;
      append(item, node('p', 'article-text', claim.text), tag(claim.epistemic_basis === 'advisory_recommendation' ? '조건부 추천 · 확정 결정 아님' : 'accepted K 근거'));
      for (const value of claim.assumptions) item.append(node('p', 'review-reason', `가정: ${value}`));
      for (const value of claim.limitations) item.append(node('p', 'review-reason', `한계: ${value}`));
      const citations = node('div', 'knowledge-flags');
      for (const revision of claim.k_revision_ids) {
        citations.append(button(`K Revision ${revision}`, 'exact-link', () => openKnowledge(revision, storeId)));
      }
      item.append(citations);
      const binding = parchment.citations.find(value => value.section_index === index)?.claims.find(value => value.claim_key === claim.claim_key);
      for (const ref of binding?.effective_edge_refs || []) {
        const relation = details(`Effective Edge ${ref.semantic_kedge_revision_id}`);
        relation.append(node('pre', 'evidence-quote', JSON.stringify(ref, null, 2))); item.append(relation);
      }
      block.append(item);
    }
    const recommendation = section.answer_or_payload.recommendation;
    if (recommendation) {
      const comparison = details('검토한 선택지와 추천');
      for (const option of recommendation.options) comparison.append(node('p', 'review-reason', `${option.option_key}: ${option.label}`));
      comparison.append(node('p', 'review-reason', `기준: ${recommendation.criteria.join(' · ')}`));
      for (const value of recommendation.comparison) comparison.append(node('p', 'review-reason', `${value.option_key} · ${value.criterion} · 설명 ${value.claim_keys.join(', ')}`));
      comparison.append(node('p', 'review-reason', `추천 선택지: ${recommendation.recommended_option ?? '지정하지 않음'}`)); block.append(comparison);
    }
    for (const value of section.answer_or_payload.unresolved) block.append(node('p', 'review-notice', `미해결: ${value}`));
    if (section.answer_or_payload.status === 'insufficient') block.append(tag('근거 부족을 명시한 설명', 'held'));
    article.append(block);
  }
  fragment.append(article);
  const provenance = details('Parchment 구성 이력');
  provenance.append(keyValues([['Parchment', parchment.parchment_id], ['Snapshot SHA-256', parchment.snapshot_sha256], ['구성 작업', parchment.provenance.operation], ['구성 actor', parchment.provenance.actor], ['생성 시각', parchment.created_at]]));
  for (const section of parchment.body.sections) provenance.append(keyValues([['Wisdom', section.wisdom_id], ['Wisdom snapshot SHA-256', section.wisdom_snapshot_sha256]]));
  fragment.append(provenance); $('content').replaceChildren(fragment);
}
function renderPage(data) {
  const page = data.page;
  const historical = page.snapshot_id !== data.current_snapshot_id;
  setCrumb('위키 문서', page.kind === 'paper' ? sourceLabel(page) : '주제 문서');
  const fragment = document.createDocumentFragment();
  append(fragment, append(node('div', 'document-topline'), node('span', 'eyebrow', page.kind === 'paper' ? `${sourceFormat(page) === 'code' ? 'CODE' : 'SOURCE'} / LEGACY EXPLANATION` : 'TOPIC / LEGACY EXPLANATION'), historySelect(data)), node('h1', `document-title ${page.kind === 'topic' ? 'topic-title' : ''}`, page.title));
  const meta = node('div', 'document-meta');
  if (page.kind === 'paper') {
    const summary = sourcePage(page.data_id);
    append(meta, node('span', 'meta-chip', sourceLabel(page)), node('span', '', `${page.items.length}개 본문 항목`), node('span', 'meta-dot', '·'), node('span', '', `${summary?.information_count ?? '—'}개 Information`));
    const doi = page.metadata?.doi;
    if (doi) append(meta, node('span', 'meta-dot', '·'), node('span', '', `DOI ${doi}`));
  } else append(meta, node('span', 'meta-chip', '주제 문서'), node('span', '', `${page.contributions.length}개 자료 연결`));
  if (historical) meta.append(node('span', 'meta-chip', '과거 snapshot'));
  meta.append(node('span', 'meta-chip', '기존 I 기반 설명'));
  fragment.append(meta);
  if (page.scope) fragment.append(node('p', 'scope-text', page.scope));
  fragment.append(node('div', 'paper-rule'));
  const paper = node('article', 'article-paper');
  append(paper, append(node('div', 'article-note'), node('span', 'small-symbol', '↗'), node('span', '', '문장 옆 인용 번호를 누르면 원문과 근거를 확인할 수 있습니다.')));
  const counter = { value: 0 };
  if (page.kind === 'paper') renderSections(paper, page.items, counter, sourceFormat(page));
  else for (const [index, contribution] of page.contributions.entries()) {
    const section = node('section', 'contribution');
    const reference = (data.topic_sources || []).find((source) => source.data_id === contribution.paper_data_id && source.page_id === contribution.paper_page_id);
    const heading = node('div', 'contribution-source');
    append(heading, node('span', 'source-number', String(index + 1).padStart(2, '0')));
    heading.append(reference ? button(contribution.paper_title, '', () => openPage(reference.page_id, reference.snapshot_id), '이 문서에 연결된 자료 snapshot 열기') : node('span', '', contribution.paper_title));
    section.append(heading); renderSections(section, contribution.items, counter, sourceFormat({ data_id: contribution.paper_data_id })); paper.append(section);
  }
  fragment.append(paper);
  append(fragment, append(node('div', 'document-foot'), node('span', '', '기존 설명 구성 · I 기반 생성 이력과 인용을 보존합니다'), node('code', '', `Snapshot ${short(page.snapshot_id)}…`)));
  fragment.append(renderKnowledge(data.related));
  const provenance = details('문서 이력과 식별 정보');
  provenance.append(node('p', 'review-reason', '이 문서는 I를 근거로 생성한 기존 설명 구성입니다. K 자체의 문구가 아니며, 새 K2W·W2P 실행이나 W/P 식별자를 소급해서 부여하지 않았습니다.'));
  provenance.append(keyValues([['Page', page.page_id], ['Snapshot', page.snapshot_id], ['이전 Snapshot', page.previous_snapshot_id || '없음'], ['Import', data.import_id || '이 snapshot의 DB checkpoint 없음'], ...(page.data_id ? [['Data', page.data_id], ['Source 실행', page.source_execution_id]] : [])]));
  fragment.append(provenance);
  $('content').replaceChildren(fragment);
}
function renderSections(container, items, counter, format) {
  const sectionLabels = format === 'code' ? { ...labels, methods: '구현과 동작', findings: '명시된 동작', results: '명시된 동작', limitations: '제약과 한계' } : labels;
  const order = ['overview', 'methods', 'findings', 'results', 'limitations', 'unresolved'];
  const sections = [...new Set(items.map((item) => item.section || 'findings'))].sort((a, b) => (order.indexOf(a) === -1 ? 99 : order.indexOf(a)) - (order.indexOf(b) === -1 ? 99 : order.indexOf(b)));
  for (const [index, name] of sections.entries()) {
    const section = node('section', 'article-section');
    append(section, append(node('div', 'section-heading'), node('span', 'section-number', String(index + 1).padStart(2, '0')), node('h2', '', sectionLabels[name] || name)));
    for (const item of items.filter((item) => (item.section || 'findings') === name)) {
      const entry = node('div', 'article-item');
      entry.dataset.itemKey = item.item_key;
      const text = node('p', 'article-text', item.text);
      text.append(citationButtons(item.evidence || [], counter));
      entry.append(text);
      const links = node('div', 'item-topics');
      for (const key of item.topic_keys || []) {
        const topic = state.pages.find((p) => p.topic_key === key && p.page_id !== state.page?.page_id && (!state.unified || p.store_id === state.storeId));
        if (topic) links.append(button(`# ${topic.title}`, 'topic-link', () => openPage(topic.page_id)));
      }
      if (links.childElementCount) entry.append(links);
      section.append(entry);
    }
    container.append(section);
  }
}
function citationButtons(evidence, counter) {
  const citations = node('span', 'citations');
  for (const item of evidence) {
    const number = ++counter.value;
    const pages = item.page_numbers || (item.page_number ? [item.page_number] : []);
    const location = pages.length ? `${pages.join(', ')}페이지` : '정확한 원문 위치';
    const citation = button(String(number), 'citation', () => openEvidence(item), `${sourceName(item.data_id)} · ${location} · 근거 ${number}`);
    citation.setAttribute('aria-label', `근거 ${number}, ${location} 원문 보기`);
    citations.append(citation);
  }
  return citations;
}
function renderKnowledge(related = {}) {
  const panel = details(`연결된 Knowledge · ${related.links?.length || 0}`);
  panel.append(node('p', '', '같은 원문 근거를 공유하는 연결입니다. 각 Knowledge의 의미적 지지 관계를 판정한 표시는 아닙니다.'));
  if (related.review_required_links) panel.append(node('p', '', `별도 검토가 필요한 연결 ${related.review_required_links}개는 기본 목록에서 제외되어 있습니다.`));
  if (related.unavailable_reason) panel.append(node('p', '', '이 과거 snapshot에 대응하는 DB checkpoint가 없어 Knowledge 연결을 표시하지 않습니다.'));
  for (const link of related.links || []) {
    const card = node('div', 'knowledge-card');
    const snapshot = link.node_snapshot || {};
    const origin = snapshot.generation_origin;
    const originText = origin?.is_inferred === true ? '추론에서 생성' : origin?.is_inferred === false ? '원문에서 생성' : '생성 기원 미기록';
    append(card, append(node('div', 'knowledge-flags'), tag('shared_source_evidence'), tag(originText), tag(link.is_current_now === false ? '과거 Revision' : link.is_current_now === true ? '현재 Revision' : '현재 여부 미확인')), node('p', '', snapshot.statement || snapshot.title || '저장된 Knowledge'), node('code', '', `Revision ${link.knode_revision_id || snapshot.knode_revision_id || '알 수 없음'}`));
    if (origin?.origin_operation) card.append(node('p', '', `생성 작업: ${origin.origin_operation}`));
    const revision = link.knode_revision_id || snapshot.knode_revision_id;
    if (revision) card.append(button('생성 기원과 정확한 지식 Revision 보기', 'exact-link', () => openKnowledge(revision)));
    panel.append(card);
  }
  return panel;
}
function closeSource() {
  ++state.sourceTicket;
  $('source-panel').hidden = true;
  state.evidence = null; state.information = null; state.pdfOpened = false;
  if (pdfViewer) { pdfViewer.destroy(); pdfViewer = null; }
  $('pdf-canvas').replaceChildren();
  $('pdf-tab').hidden = false;
  $('information-tab').textContent = 'Information';
}
async function openEvidence(evidence) {
  const storeId = evidence.store_id || state.storeId;
  if (state.unified && storeId !== state.storeId) selectStore(storeId);
  evidence = { ...evidence, ...(state.unified ? { store_id: storeId, sourceOnly: state.data.some(source => source.store_id === storeId && source.data_id === evidence.data_id) || evidence.sourceOnly } : {}) };
  if (evidence.grounding_type === 'data') return openDataEvidence(evidence);
  closeSource();
  const ticket = ++state.sourceTicket;
  state.evidence = { ...evidence };
  $('source-panel').hidden = false;
  $('source-label').textContent = sourceName(evidence.data_id);
  $('information-view').replaceChildren(node('p', 'information-text', '정확한 Information과 원문 위치를 불러오고 있습니다.'));
  state.pdfPage = evidence.page_numbers?.[0] || evidence.page_number || (evidence.source_refs?.[0]?.page_index ?? 0) + 1;
  state.pdfCount = null;
  $('pdf-page').value = state.pdfPage; $('pdf-total').textContent = '';
  sourceStatus(); selectSourceTab(evidence.information_id ? 'information' : 'pdf', false);
  try {
    if (evidence.information_id) {
      if (!evidence.source_execution_id) throw new Error('이 Information 인용의 정확한 source 실행 식별자가 없습니다. 저장된 근거 연결을 확인해야 합니다.');
      const information = evidence.sourceOnly ? await request('source_information', { data_id: evidence.data_id, information_id: evidence.information_id, source_execution_id: evidence.source_execution_id }, storeId)
        : await request('information', { information_id: evidence.information_id, source_execution_id: evidence.source_execution_id }, storeId);
      if (ticket !== state.sourceTicket) return;
      if (evidence.sourceOnly) information.sourceOnly = true;
      if (state.unified) information.store_id = storeId;
      state.information = information; renderInformation(information, evidence, ticket);
    } else {
      $('information-view').replaceChildren(node('p', 'information-text', '이 인용은 등록 원본 페이지를 직접 확인한 근거입니다. 연결된 Information 인용을 새로 만들지 않습니다.'), keyValues([['Data', evidence.data_id], ['원본 페이지', state.pdfPage], ['근거 ID', evidence.evidence_id || '원본 페이지']]));
    }
    if (state.sourceTab === 'pdf') await loadPdf(ticket);
  } catch (error) { if (ticket === state.sourceTicket) sourceStatus(errorText(error)); }
}
async function openDataEvidence(evidence) {
  closeSource();
  const ticket = ++state.sourceTicket;
  state.evidence = { ...evidence };
  $('source-panel').hidden = false;
  $('source-label').textContent = sourceName(evidence.data_id);
  $('information-tab').textContent = '원문 D';
  $('pdf-tab').hidden = true;
  selectSourceTab('information', false); sourceStatus();
  $('information-view').replaceChildren(node('p', 'information-text', '등록 원문과 정확한 D2K 근거를 확인하고 있습니다.'));
  try {
    const result = await request('data_grounding', { grounding_id: evidence.grounding_id });
    if (ticket !== state.sourceTicket) return;
    const { grounding, view, original } = result;
    if (result.read_only !== true || result.source_info !== null || grounding?.grounding_id !== evidence.grounding_id
        || grounding.data_id !== evidence.data_id || view?.data_id !== grounding.data_id
        || view.view_id !== grounding.view_id || original?.sha256 !== grounding.data_id) throw new Error('원문 근거의 Data·view 결속이 일치하지 않습니다.');
    const fragment = document.createDocumentFragment();
    append(fragment, append(node('div', 'knowledge-flags'), tag('D2K · 등록 원문 근거'), tag(evidence.evidence_basis === 'transitive' ? '전제의 원문' : '직접 원문')),
      node('p', 'review-reason', '이 근거는 별도로 요청한 D2K 실행에서 원문 D를 직접 검토한 기록입니다.'),
      keyValues([['Data', grounding.data_id], ['근거', grounding.grounding_id], ['근거 Record', grounding.origin_record_id],
        ['정확한 KRevision', grounding.node_revision_id], ['View', grounding.view_id], ['원문 보기 준비', result.preparation_id]]));
    if (result.media_kind === 'text' && view.kind === 'text' && typeof view.text === 'string') {
      const location = grounding.locator, sourceRange = view.locator;
      append(fragment, keyValues([['인용 원본 bytes', `[${location.byte_start}, ${location.byte_end})`],
        ['인용 원본 줄', `${location.line_start}–${location.line_end}`],
        ['보존한 원문 범위', `bytes [${sourceRange.byte_start}, ${sourceRange.byte_end}) · 줄 ${sourceRange.line_start}–${sourceRange.line_end}`]]),
        node('span', 'excerpt-label', '검증된 원문 인용'), node('pre', 'quote-box code-text', grounding.quote));
      const full = details('보존된 원문 보기 전체', 'provenance');
      const text = node('pre', 'information-text code-text');
      const points = Array.from(view.text), start = grounding.char_start, end = grounding.char_end;
      if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || start >= end || end > points.length
          || points.slice(start, end).join('') !== grounding.quote) throw new Error('원문 인용 범위가 보존된 보기와 다릅니다.');
      append(text, document.createTextNode(points.slice(0, start).join('')), node('mark', '', points.slice(start, end).join('')), document.createTextNode(points.slice(end).join('')));
      full.append(text); fragment.append(full);
    } else if (result.media_kind === 'pdf' && view.kind === 'pdf_page') {
      if (result.image?.media_type !== 'image/png' || result.image.sha256 !== view.image_sha256
          || grounding.media_sha256 !== view.image_sha256) throw new Error('보존된 원문 페이지 이미지의 hash가 다릅니다.');
      const picture = node('img', 'source-image');
      picture.src = `data:image/png;base64,${result.image.base64}`;
      picture.alt = `등록 원본 PDF ${view.page_index + 1}페이지에서 보존한 이미지`;
      append(fragment, keyValues([['원본 PDF 페이지', `${view.page_index + 1} / ${view.page_count}`],
        ['좌표계', grounding.locator.coordinate_system], ['보존 이미지 SHA', view.image_sha256]]), picture,
        node('p', 'source-image-caption', '원본 PDF에서 보존한 페이지 이미지 · Information 인용을 만들지 않습니다.'));
    } else throw new Error('지원하지 않는 D2K 원문 보기 형식입니다.');
    const binding = details('등록 원본과 좌표 정보', 'provenance');
    append(binding, keyValues([['원본 SHA-256', original.sha256], ['원본 bytes', original.byte_size], ['형식', original.media_type]]),
      node('pre', 'evidence-quote', JSON.stringify(grounding.locator, null, 2)));
    fragment.append(binding); $('information-view').replaceChildren(fragment);
  } catch (error) { if (ticket === state.sourceTicket) sourceStatus(errorText(error)); }
}
function renderInformation(information, evidence, ticket) {
  const container = $('information-view');
  const fragment = document.createDocumentFragment();
  const contexts = information.code_context ? [information.code_context].flat() : (information.source_refs || []).map((ref) => ref.code_context).filter(Boolean);
  const code = information.source_format === 'code' || contexts.length > 0 || sourceFormat(information) === 'code';
  const pdf = information.original?.media_type === 'application/pdf';
  $('pdf-tab').hidden = code || (information.original?.media_type && !pdf);
  if ($('pdf-tab').hidden) selectSourceTab('information', false);
  append(fragment, append(node('div', 'knowledge-flags'), tag(code ? 'Code I' : information.kind === 'image' ? 'Image I' : 'Text I'), ...(code || (information.original?.media_type && !pdf) ? [] : [tag(`${(evidence.page_numbers?.length ? evidence.page_numbers : [state.pdfPage]).join(', ')} 페이지`)])), node('h3', 'source-unit-title', information.title));
  for (const context of contexts) {
    const range = context.member_text_range;
    fragment.append(keyValues([['파일', context.member_path || 'Dossier metadata'], ['파일 줄', range ? `${range.line_start}–${range.line_end}` : '메타데이터'], ['파일 byte 범위', range ? `[${range.byte_start}, ${range.byte_end})` : '메타데이터'], ['상위 정의', (context.enclosing_symbols || []).map((symbol) => symbol.qualified_name).join(', ') || 'module'], ['구조 해석', context.parse_status || context.representation_role]]));
  }
  if (evidence.quote) append(fragment, node('span', 'excerpt-label', '인용된 원문'), node(code ? 'pre' : 'blockquote', code ? 'quote-box code-text' : 'quote-box', evidence.quote));
  if (information.content) {
    const full = details('Information 전체 내용', 'provenance');
    if (evidence.sourceOnly) full.open = true;
    const text = node(code ? 'pre' : 'div', code ? 'information-text code-text' : 'information-text');
    const points = Array.from(information.content);
    const start = evidence.char_start; const end = evidence.char_end;
    if (Number.isInteger(start) && Number.isInteger(end) && 0 <= start && start < end && end <= points.length) {
      append(text, document.createTextNode(points.slice(0, start).join('')), node('mark', '', points.slice(start, end).join('')), document.createTextNode(points.slice(end).join('')));
    } else text.textContent = information.content;
    full.append(text); fragment.append(full);
  }
  if (!evidence.quote && !information.content) fragment.append(node('p', 'information-text', '이미지로 보존된 Information입니다. 원본 PDF와 보존 이미지를 함께 확인할 수 있습니다.'));
  const media = evidence.media_sha256 ? information.media?.filter((item) => item.sha256 === evidence.media_sha256) : information.kind === 'image' || evidence.sourceOnly ? information.media : [];
  const images = node('div');
  fragment.append(images);
  for (const item of media || []) loadEvidenceImage(item, information, images, ticket);
  const provenance = details('정확한 원문 연결', 'provenance');
  provenance.append(keyValues([['Data', information.data_id], ['Information', information.information_id], ['Source 실행', information.source_execution_id], ['문자 범위', Number.isInteger(evidence.char_start) ? `[${evidence.char_start}, ${evidence.char_end}) · Unicode codepoints` : '이미지 또는 원본 페이지'], ['원문 블록', evidence.source_block_id || '전체 Information'], ['원본 SHA-256', information.original?.sha256], ['원문 위치', '보존된 블록·leaf 영역']]));
  if (evidence.sourceOnly) provenance.append(node('pre', 'evidence-quote', JSON.stringify(information.source_refs || [], null, 2)));
  fragment.append(provenance); container.replaceChildren(fragment);
}
async function loadEvidenceImage(media, information, container, ticket) {
  try {
    const result = await request(information.sourceOnly ? 'source_artifact' : 'artifact', { ...(information.sourceOnly ? {} : { kind: 'image' }), data_id: information.data_id, sha256: media.sha256, source_execution_id: information.source_execution_id }, information.store_id || state.storeId);
    if (ticket !== state.sourceTicket) return;
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(result.media_type)) throw new Error('지원하지 않는 보존 이미지 형식입니다.');
    const image = node('img', 'source-image'); image.src = `data:${result.media_type};base64,${result.base64}`;
    image.alt = `${information.title} · 보존된 원문 이미지`;
    append(container, image, node('p', 'source-image-caption', `보존 이미지 · ${short(result.sha256, 16)}…`));
  } catch (error) { if (ticket === state.sourceTicket) container.append(node('p', 'source-image-caption', errorText(error))); }
}
function selectSourceTab(name, load = true) {
  state.sourceTab = name;
  for (const tab of ['information', 'pdf']) {
    $(`${tab}-tab`).classList.toggle('active', tab === name);
    $(`${tab}-tab`).setAttribute('aria-selected', String(tab === name));
    $(`${tab}-view`).hidden = tab !== name;
  }
  if (name === 'pdf' && load) loadPdf(state.sourceTicket);
}
async function loadPdf(ticket) {
  if (!state.evidence || state.pdfOpened) return;
  state.pdfOpened = true;
  sourceStatus('등록 원본 파일을 검증하고 PDF를 여는 중입니다.');
  try {
    const evidence = state.evidence;
    const artifact = evidence.sourceOnly ? await request('source_artifact', { data_id: evidence.data_id }, evidence.store_id || state.storeId)
      : await request('artifact', { kind: 'original', data_id: evidence.data_id, ...(evidence.source_execution_id ? { source_execution_id: evidence.source_execution_id } : {}) }, evidence.store_id || state.storeId);
    if (ticket !== state.sourceTicket) return;
    if (artifact.media_type !== 'application/pdf') throw new Error('이 원본은 PDF 문서가 아닙니다.');
    const host = node('div', 'pdf-host');
    $('pdf-canvas').replaceChildren(host);
    pdfViewer = new PdfPanel(host);
    const result = await pdfViewer.open({ base64: artifact.base64, pageNumber: state.pdfPage, regions: evidence.source_refs || [], dataId: evidence.data_id });
    if (ticket !== state.sourceTicket) return;
    state.pdfCount = result?.pageCount || pdfViewer.pageCount || null;
    $('pdf-total').textContent = state.pdfCount ? `/ ${state.pdfCount}` : '';
    if (state.pdfCount) $('pdf-page').max = state.pdfCount; else $('pdf-page').removeAttribute('max');
    sourceStatus();
  } catch (error) {
    if (ticket !== state.sourceTicket) return;
    state.pdfOpened = false; sourceStatus(errorText(error));
  }
}
async function changePdfPage(number) {
  if (!pdfViewer || !Number.isInteger(number) || number < 1 || (state.pdfCount && number > state.pdfCount)) return;
  const ticket = state.sourceTicket;
  const pageTicket = ++state.pdfTicket;
  state.pdfPage = number;
  $('pdf-page').value = number;
  try { await pdfViewer.renderPage(number); if (ticket === state.sourceTicket && pageTicket === state.pdfTicket) sourceStatus(); }
  catch (error) { if (ticket === state.sourceTicket && pageTicket === state.pdfTicket) sourceStatus(errorText(error)); }
}
function reviewState(value) {
  return ({ prepared: '입력 준비됨', proposed: '검증 대기', needs_human: '검토 필요', failed: '실행 실패', completed: '검토 완료', zero_output: '검토 완료 · 결과 없음', needs_review: '검토 필요', reviewed: '검토됨', confirmed: '확인됨', accepted_new: '새 지식 반영', accepted_revision: '의미 개정 반영', reused: '동일 의미 재사용', no_material_delta: '의미 변경 없음', rejected: '반영하지 않음', unavailable: '원문 제공 불가', pending: '대기', provided: '원문 제공됨' })[value] || value || '미기록';
}
function knowledgeFlags(knowledge) {
  const origin = knowledge.generation_origin;
  const flags = append(node('div', 'knowledge-flags'), tag(knowledge.kind === 'observation' ? '관찰' : knowledge.kind === 'proposition' ? '명제' : knowledge.kind), tag(origin?.is_inferred === true ? '추론으로 생성' : origin?.origin_operation === 'd2k' ? 'D2K · 원문 D에서 생성' : origin?.is_inferred === false ? '원문 I에서 생성' : '생성 기원 미기록'));
  const current = knowledge.is_current_now ?? (knowledge.current_revision_id ? knowledge.current_revision_id === knowledge.knode_revision_id : null);
  flags.append(tag(current === true ? '현재 Revision' : current === false ? '과거 Revision' : '정확한 Revision'));
  if (knowledge.source_version_status) flags.append(tag(({ current: '현재 자료 버전 근거', historical: '과거 자료 버전 근거', untracked: '자료 버전 미연결' })[knowledge.source_version_status] || knowledge.source_version_status, knowledge.source_version_status === 'historical' ? 'held' : ''));
  if (knowledge.current_applicability) flags.append(tag(knowledge.current_applicability === 'needs_revalidation' ? '전제 재검토 필요' : knowledge.current_applicability === 'current_premises' ? '전제 Revision 일치' : knowledge.current_applicability, knowledge.current_applicability === 'needs_revalidation' ? 'held' : ''));
  if (knowledge.epistemic_projection === 'contested') flags.append(tag('상충 주장 있음', 'held'));
  else if (knowledge.epistemic_projection === 'uncontested') flags.append(tag('활성 상충 관계 없음'));
  return flags;
}
function versionList(versions = []) {
  const list = node('div', 'version-list');
  for (const version of versions) {
    const row = node('div', 'version-row');
    append(row, tag(version.is_head === true ? '현재 자료 버전' : version.is_head === false ? '과거 자료 버전' : '고정된 자료 버전'), node('span', '', version.label || version.name || short(version.version_id)), node('code', '', version.version_id));
    if (version.data_id) row.append(node('small', '', `Data ${version.data_id}`));
    list.append(row);
  }
  return list;
}
async function showKnowledge(cached = false) {
  const ticket = ++state.pageTicket; state.mode = 'knowledge'; state.nodeRevisionId = null;
  closeSource(); notice(); updateNavigation(); loading('지식과 자료 버전을 읽는 중입니다');
  try {
    const data = cached === true ? { nodes: state.knowledge, sources: state.sources, data_versions: state.versions } : state.unified ? await acrossStores('knowledge_catalog', ['nodes', 'sources', 'data_versions'], null) : await request('knowledge_catalog');
    if (ticket !== state.pageTicket) return;
    state.knowledge = data.nodes; state.sources = data.sources || []; state.versions = data.data_versions || []; updateNavigation();
    setCrumb('지식', '생성 기원과 근거');
    const fragment = document.createDocumentFragment();
    append(fragment, node('span', 'eyebrow', 'KNOWLEDGE / ORIGIN & EVIDENCE'), node('h1', 'query-list-title', '지식 K'), node('p', 'query-intro', '저장된 K 문구와 정확한 Revision에서 생성 기원, 전제와 원문 근거를 읽습니다. 위키의 설명 문서와 구분하며, 자료 버전의 현재 여부와 지식의 검토 상태는 별도로 표시합니다.'));
    const selectedVersions = visibleRows(state.versions), selectedKnowledge = visibleRows(state.knowledge).filter(row => row.statement.toLocaleLowerCase().includes(state.search.toLocaleLowerCase()));
    if (selectedVersions.length) { const versions = details(`자료 버전 · ${selectedVersions.length}`); versions.append(versionList(selectedVersions)); fragment.append(versions); }
    for (const knowledge of selectedKnowledge) {
      const card = button('', 'query-card knowledge-result', () => openKnowledge(knowledge.knode_revision_id, knowledge.store_id));
      append(card, knowledgeFlags(knowledge), node('p', '', knowledge.statement), node('code', 'revision-id', knowledge.knode_revision_id)); fragment.append(card);
    }
    if (!selectedKnowledge.length) fragment.append(node('p', 'query-intro', '선택한 Realm과 검색 조건에 해당하는 지식이 없습니다.'));
    $('content').replaceChildren(fragment); $('main').scrollTop = 0;
  } catch (error) { if (ticket === state.pageTicket) empty('지식을 읽지 못했습니다', errorText(error), showKnowledge); }
}
async function openKnowledge(revisionId, storeId = state.storeId) {
  selectStore(storeId);
  const ticket = ++state.pageTicket; state.mode = 'knowledge'; state.nodeRevisionId = revisionId;
  closeSource(); notice(); updateNavigation(); loading('정확한 지식 Revision을 읽는 중입니다');
  try {
    const data = await request('knowledge_node', { node_revision_id: revisionId });
    if (ticket !== state.pageTicket) return;
    renderKnowledgeNode(data); $('main').scrollTop = 0;
  } catch (error) { if (ticket === state.pageTicket) empty('지식 Revision을 열지 못했습니다', errorText(error), () => openKnowledge(revisionId)); }
}
function renderKnowledgeNode(data) {
  const knowledge = data.node, origin = knowledge.generation_origin || {};
  setCrumb('지식', '정확한 Revision');
  const fragment = document.createDocumentFragment();
  append(fragment, button('‹ 지식 목록', 'back-button', showKnowledge), node('div', 'eyebrow', 'EXACT KNOWLEDGE REVISION'), node('h1', 'knowledge-title', knowledge.statement), knowledgeFlags(knowledge), keyValues([['Knowledge', knowledge.knode_id], ['Revision', knowledge.knode_revision_id], ['생성 작업', origin.origin_operation], ['생성 Record', origin.origin_record_id || knowledge.origin_record_id]]));
  if (origin.is_inferred === true) {
    const explanation = node('section', 'review-block');
    append(explanation, node('h2', '', '추론의 근거와 한계'), node('p', 'article-text', origin.derivation_basis || '저장된 도출 설명이 없습니다.'), keyValues([['추론 유형', origin.inference_type]]));
    for (const [label, values] of [['가정', origin.assumptions], ['한계', origin.limitations]]) {
      explanation.append(node('h3', '', label));
      for (const value of Array.isArray(values) ? values : values ? [values] : ['기록 없음']) explanation.append(node('p', 'review-reason', typeof value === 'string' ? value : JSON.stringify(value)));
    }
    fragment.append(explanation);
  }
  const premises = data.premise_nodes || knowledge.premise_nodes || [];
  if (premises.length) {
    const section = node('section', 'review-block'); section.append(node('h2', '', '도출에 사용한 정확한 전제'));
    for (const premise of premises) {
      const card = button('', 'query-card premise-link', () => openKnowledge(premise.knode_revision_id));
      append(card, node('p', '', premise.statement), node('code', 'revision-id', premise.knode_revision_id)); section.append(card);
    }
    fragment.append(section);
  }
  const supports = knowledge.data_version_supports || data.data_version_supports || [];
  if (supports.length) {
    const section = details('생성 버전과 추가 근거 버전');
    for (const support of supports) {
      section.append(node('p', '', `${support.record_id === (origin.origin_record_id || knowledge.origin_record_id) ? '최초 생성 근거' : '추가로 검증된 근거'} · ${support.operation || ''} · Record ${support.record_id}`));
      section.append(versionList((support.versions || support.version_ids?.map((id) => ({ version_id: id })) || []).map((version) => ({ ...state.versions.find((row) => row.version_id === version.version_id), ...version }))));
    }
    fragment.append(section);
  }
  const evidence = data.evidence || knowledge.evidence || [];
  const dataEvidence = data.data_evidence || [...(knowledge.direct_data_groundings || []).map(row => ({ ...row, evidence_basis: 'direct' })), ...(knowledge.transitive_data_refs || []).map(row => ({ ...row, evidence_basis: 'transitive' }))];
  const evidenceSection = node('section', 'review-block');
  append(evidenceSection, node('h2', '', origin.is_inferred === true ? '전제를 통해 연결된 원문 근거' : '원문 근거'), node('p', 'query-intro', origin.is_inferred === true ? '추론의 생성 근거는 위 전제 Revision입니다. 아래 원문 연결은 직접 인용과 전제를 통한 연결을 구분해 보존합니다.' : '검증된 지식의 실제 I 또는 D 근거에서 등록 원문으로 이동합니다.'));
  for (const item of evidence) {
    const card = node('div', 'evidence-card');
    append(card, tag(item.evidence_basis === 'transitive' || item.is_transitive === true ? '전제를 통한 원문' : item.evidence_basis === 'direct' || item.is_transitive === false ? '직접 원문 근거' : '보존된 원문 연결'), button(`${sourceName(item.data_id)} · 원문 보기`, 'evidence-link', () => openEvidence(item)), node('pre', 'evidence-quote', item.quote || '문자 인용 없음 · 정확한 Information에서 확인'), node('code', 'revision-id', item.information_id));
    evidenceSection.append(card);
  }
  for (const item of dataEvidence) {
    const card = node('div', 'evidence-card');
    append(card, tag(item.evidence_basis === 'transitive' ? '전제를 통한 D2K 원문' : 'D2K 직접 원문'),
      button(`${sourceName(item.data_id)} · D2K 원문 보기`, 'evidence-link data-evidence-link', () => openDataEvidence(item)),
      node('pre', 'evidence-quote', item.quote || `원본 PDF ${(item.locator?.page_index ?? 0) + 1}페이지 이미지`), node('code', 'revision-id', item.grounding_id));
    evidenceSection.append(card);
  }
  if (!evidence.length && !dataEvidence.length) evidenceSection.append(node('p', 'query-intro', '현재 범위에서 열 수 있는 원문 근거가 없습니다.'));
  fragment.append(evidenceSection);
  const provenance = details('직접·전이 근거와 도출 기록');
  provenance.append(keyValues([['직접 I 근거', (knowledge.direct_groundings || []).length], ['전제를 통한 I 근거', (knowledge.transitive_source_refs || []).length], ['직접 D 근거', (knowledge.direct_data_groundings || []).length], ['전제를 통한 D 근거', (knowledge.transitive_data_refs || []).length], ['보존된 도출', (knowledge.derivations || data.derivations || []).length]]));
  for (const derivation of knowledge.derivations || data.derivations || []) {
    const card = node('div', 'round-card');
    append(card, node('h3', '', `Record ${derivation.record_id}`), node('p', '', derivation.derivation_basis), node('p', '', derivation.current_applicability === 'needs_revalidation' ? '전제 변경으로 재검토 필요' : '저장된 도출 기록'));
    for (const id of derivation.premise_revision_ids || []) card.append(button(`전제 ${id}`, 'exact-link', () => openKnowledge(id)));
    provenance.append(card);
  }
  fragment.append(provenance); $('content').replaceChildren(fragment);
}
async function showReviews(cached = false) {
  const ticket = ++state.pageTicket; state.mode = 'reviews'; state.reviewId = null;
  closeSource(); notice(); updateNavigation(); loading('보존된 검토 기록을 읽는 중입니다');
  try {
    const data = cached === true ? { executions: state.reviews } : state.unified ? await acrossStores('review_catalog', ['executions', 'sources', 'data_versions']) : await request('review_catalog');
    if (ticket !== state.pageTicket) return;
    state.reviews = data.executions; updateNavigation(); setCrumb('검토', '원문 검토 기록');
    const fragment = document.createDocumentFragment();
    append(fragment, node('span', 'eyebrow', 'SOURCE REVIEW / RETAINED OUTCOMES'), node('h1', 'query-list-title', '검토'), node('p', 'query-intro', '각 실행 당시의 검토 상태와 실제 판단 이유를 확인합니다. 이후 실행이 완료되어도 과거 실행의 미해결 수와 기록은 그대로 보존됩니다.'));
    for (const review of visibleRows(state.reviews).filter(row => `${sourceName(row.data_id, row.store_id)} ${reviewState(row.state)}`.toLocaleLowerCase().includes(state.search.toLocaleLowerCase()))) {
      const card = button('', 'query-card review-result', () => openReview(review.execution_id, review.store_id));
      append(card, append(node('div', 'knowledge-flags'), tag(reviewState(review.state), ['completed', 'zero_output'].includes(review.state) ? 'accepted' : 'held'), tag((review.operation || 'i2k').toUpperCase())), node('p', '', sourceName(review.data_id, review.store_id)), node('p', 'review-counts', `이 실행 당시 · 미해결 I ${review.pending_information_count ?? '—'} · 원문 구간 ${review.pending_target_count ?? '—'} · 내용 항목 ${review.pending_item_count ?? '—'}`), node('code', 'revision-id', review.execution_id)); fragment.append(card);
    }
    if (!state.reviews.length) fragment.append(node('p', 'query-intro', '이 자료 범위에 저장된 I2K 검토가 없습니다.'));
    $('content').replaceChildren(fragment); $('main').scrollTop = 0;
  } catch (error) { if (ticket === state.pageTicket) empty('검토 기록을 읽지 못했습니다', errorText(error), showReviews); }
}
async function openReview(executionId, storeId = state.storeId) {
  selectStore(storeId);
  const ticket = ++state.pageTicket; state.mode = 'reviews'; state.reviewId = executionId;
  closeSource(); notice(); updateNavigation(); loading('원문별 검토 이유를 읽는 중입니다');
  try {
    const data = await request('review_status', { execution_id: executionId });
    if (ticket !== state.pageTicket) return;
    renderReview(data); $('main').scrollTop = 0;
  } catch (error) { if (ticket === state.pageTicket) empty('검토 기록을 열지 못했습니다', errorText(error), () => openReview(executionId)); }
}
function reviewEvidence(review, informationId, dataId, anchor = {}) {
  const source = (review.sources || []).find((row) => row.data_id === dataId);
  return { information_id: informationId, data_id: dataId, source_execution_id: source?.source_execution_id, ...anchor };
}
function informationErrorNotice(review) {
  const report = review.information_errors;
  if (report?.schema_version !== 'i2k-information-errors-v1' || report.requires_user_review !== true
      || !Array.isArray(report.errors) || !report.errors.length) return null;
  if (report.execution_id !== review.execution_id) return node('p', 'review-notice', '이 실행과 정보 오류 보고의 연결을 확인하지 못했습니다.');
  const section = node('section', 'review-block information-errors');
  append(section, node('h2', '', 'D2I 정보 오류 · 사용자 확인 필요'),
    node('p', 'review-reason', '모델이 보고한 Information 오류입니다. 원문 누락·전사·구조 오류 여부는 사실 확인을 기다리고 있습니다.'));
  if (report.d2i_calls === 0 && report.direct_source_compilation_allowed === false) {
    section.append(node('p', 'review-notice', '관련 K 보류 · D2I 자동 재실행 없음 · 원문에서 K 우회 생성 없음'));
  } else section.append(node('p', 'review-notice', '오류 보고의 자동 처리 금지 상태를 확인하지 못했습니다. 실행 기록을 확인하세요.'));
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
  for (const error of report.errors) {
    const card = node('div', 'review-item information-error');
    append(card, append(node('div', 'knowledge-flags'), tag(error.reported_by === 'validator' ? '독립 검토 모델 보고' : error.reported_by === 'generator' ? '생성 모델 보고' : '보고 주체 미확인'),
      tag(error.status === 'reported_error' ? '보고된 오류' : `보고 상태 · ${error.status || '미기록'}`, 'held'),
      tag(error.verification_status === 'verification_pending' ? '사실 확인 대기' : `확인 상태 · ${error.verification_status || '미기록'}`, 'held')),
      node('p', 'review-reason', error.reason), node('code', 'revision-id', (error.reason_codes || []).join(', ')),
      keyValues([['Data', error.data_id], ['Source 실행', error.source_execution_id], ['Source profile', error.source_profile_id],
        ['Source 입력 hash', error.source_input_sha256], ['관련 원문 요청', error.source_request_id || '없음']]));
    if (error.contradictory_verdict === true) card.append(node('p', 'review-notice', '독립 검토 응답의 판정과 D2I 오류 코드가 충돌합니다. 관련 K는 확인이 끝날 때까지 보류됩니다.'));
    for (const id of error.information_ids || []) {
      const valid = typeof id === 'string' && uuid.test(id) && typeof error.source_execution_id === 'string'
        && uuid.test(error.source_execution_id) && typeof error.data_id === 'string' && /^[0-9a-f]{64}$/.test(error.data_id);
      if (valid) card.append(button(`I ${id} · 보존된 내용과 원문 위치 보기`, 'evidence-link', () => openEvidence({
        information_id: id, data_id: error.data_id, source_execution_id: error.source_execution_id })));
      else card.append(node('code', 'revision-id', `Information ${id ?? '식별자 미기록'} · 읽기 연결을 확인해야 합니다.`));
    }
    if (error.source_refs?.length) {
      const addresses = details('보고에 보존된 원문 주소', 'provenance');
      addresses.append(node('pre', 'code-text', JSON.stringify(error.source_refs, null, 2))); card.append(addresses);
    }
    section.append(card);
  }
  return section;
}
function renderReview(review) {
  setCrumb('검토', reviewState(review.state));
  const fragment = document.createDocumentFragment();
  append(fragment, button('‹ 검토 목록', 'back-button', showReviews), node('div', 'eyebrow', 'SOURCE REVIEW / EXACT EXECUTION'), node('h1', 'knowledge-title', sourceName(review.data_id)), append(node('div', 'knowledge-flags'), tag(`이 실행 당시 · ${reviewState(review.state)}`, ['completed', 'zero_output'].includes(review.state) ? 'accepted' : 'held'), tag(!review.data_versions?.length ? '자료 버전 미연결' : review.data_version_mode === 'pinned' ? '고정한 과거·비교 범위' : '현재 자료 버전 확인')), node('p', 'query-intro', `이 실행 당시 · 미해결 I ${review.pending_information_ids?.length || 0} · 원문 구간 ${review.pending_target_ids?.length || 0} · 내용 항목 ${review.pending_item_keys?.length || 0}`));
  if (review.next_action !== 'no_work') fragment.append(node('p', 'review-notice', '이 실행 당시의 미해결 검토를 보존한 기록입니다. 이후 실행의 완료 여부와 구분해 읽어 주세요.'));
  fragment.append(keyValues([['실행', review.execution_id], ['입력 hash', review.input_digest], ['오류', review.error_code || '기록 없음']]));
  append(fragment, informationErrorNotice(review));
  fragment.append(versionList(review.data_versions));
  const informationSection = node('section', 'review-block'); informationSection.append(node('h2', '', 'Information별 검토'));
  for (const information of review.information || []) {
    const card = details(`${reviewState(information.status)} · I ${short(information.information_id)}`, 'review-item');
    card.open = information.status === 'needs_review';
    append(card, button('정확한 원문 보기', 'evidence-link', () => openEvidence(reviewEvidence(review, information.information_id, information.data_id))), node('p', 'review-reason', `생성 검토 · ${information.generator_review?.reason || '검토 기록 없음'}`), node('p', 'review-reason', `독립 검증 · ${information.validator_review?.reason || '검증 기록 없음'}`), node('code', 'revision-id', information.information_id));
    informationSection.append(card);
  }
  fragment.append(informationSection);
  const targets = node('section', 'review-block'); targets.append(node('h2', '', '원문 구간과 내용 항목'));
  for (const target of review.targets || []) {
    const card = details(`${reviewState(target.status)} · ${target.label || target.title || short(target.target_id, 24)}`, 'review-item');
    card.open = target.status === 'needs_review';
    card.append(node('p', 'review-reason', target.validator_review?.reason || '독립 검증 기록 없음'));
    for (const item of (review.items || []).filter((row) => row.target_id === target.target_id)) {
      const entry = node('div', 'review-subitem');
      append(entry, append(node('div', 'knowledge-flags'), tag(reviewState(item.status), item.status === 'needs_review' ? 'held' : ''), node('strong', '', item.label || item.item_key)), node('p', 'review-reason', item.reason), node('p', 'review-reason', item.validator_review?.reason || '독립 검증 기록 없음'));
      for (const anchor of item.anchors || []) entry.append(button('이 항목의 원문 위치', 'evidence-link', () => openEvidence(reviewEvidence(review, item.information_id, target.data_id, anchor))));
      card.append(entry);
    }
    targets.append(card);
  }
  fragment.append(targets);
  for (const source of review.source_requests || []) fragment.append(append(node('div', 'review-notice'), node('strong', '', `원문 요청 · ${reviewState(source.status)}`), node('p', '', source.payload?.reason || source.reason || source.receipt?.reason_code || '요청 기록 보존됨')));
  const results = details(`반영·재사용한 지식 · ${review.accepted_knowledge?.length || 0}`);
  for (const record of review.accepted_knowledge || []) append(results, button(`${reviewState(record.disposition)} · ${record.result_node_revision_id}`, 'exact-link', () => openKnowledge(record.result_node_revision_id)), node('p', 'review-reason', record.reason));
  fragment.append(results);
  const history = details(`이전 검토 이력 · ${review.history?.length || 0}`);
  for (const previous of review.history || []) {
    const card = node('div', 'round-card');
    append(card, button(`${reviewState(previous.state)} · ${previous.execution_id}`, 'exact-link', () => openReview(previous.execution_id)), node('p', 'review-reason', `보존된 지식 ${previous.accepted_knowledge?.length || 0} · 미해결 I ${previous.pending_information_ids?.length || 0}`));
    history.append(card);
  }
  for (const call of review.model_calls || []) if (call.status === 'failed') history.append(node('p', 'failure-note', `실패 기록 · ${call.phase} · ${call.receipt?.structural_error_code || call.receipt?.error_code || '실행 실패'}`));
  fragment.append(history); $('content').replaceChildren(fragment);
}
function showQueries() {
  ++state.pageTicket; state.mode = 'queries'; state.queryId = null; closeSource(); notice(); updateNavigation();
  setCrumb('질문 기록', '저장된 답변');
  const fragment = document.createDocumentFragment();
  append(fragment, node('span', 'eyebrow', 'QUESTIONS / EVIDENCE & REVIEW'), node('h1', 'query-list-title', '질문 기록'), node('p', 'query-intro', '질문에 도달한 근거와 검토 과정을 다시 읽습니다. 확정된 답변과 추가 확인이 필요한 기록을 함께 보존합니다.'));
  const selectedQueries = visibleRows(state.queries).filter(row => row.question.toLocaleLowerCase().includes(state.search.toLocaleLowerCase()));
  for (const query of selectedQueries) {
    const card = button('', 'query-card', () => openQuery(query.query_id, query.store_id));
    append(card, append(node('div', 'query-card-meta'), tag(queryStates[query.state] || query.state, query.state === 'answered' ? 'accepted' : 'held'), node('span', '', `Round ${query.round}`)), node('p', '', query.question));
    fragment.append(card);
  }
  if (!selectedQueries.length) fragment.append(node('p', 'query-intro', '선택한 Realm과 검색 조건에 해당하는 질문이 없습니다.'));
  $('content').replaceChildren(fragment); $('main').scrollTop = 0;
}
async function openQuery(queryId, storeId = state.storeId) {
  selectStore(storeId);
  const ticket = ++state.pageTicket; state.mode = 'queries'; state.queryId = queryId;
  closeSource(); notice(); updateNavigation(); loading('질문 기록을 여는 중입니다');
  try {
    const data = await request('query', { query_id: queryId });
    if (ticket !== state.pageTicket) return;
    renderQuery(data); $('main').scrollTop = 0;
  } catch (error) { if (ticket === state.pageTicket) empty('질문 기록을 열지 못했습니다', errorText(error), () => openQuery(queryId)); }
}
function queryKnowledgeCitation(citation, number) {
  const origin = citation.generation_origin, support = citation.retrieval_support;
  const panel = details(`K${number} · 승인된 시스템 K2K 추론 · ${short(citation.node_revision_id)}`, 'query-knowledge-citation');
  append(panel, node('p', 'review-reason', '이 답변을 검증할 때 보존한 지식·도출·지원 경로입니다.'), node('p', 'article-text', citation.statement), button(`정확한 KRevision ${citation.node_revision_id} 열기`, 'exact-link', () => openKnowledge(citation.node_revision_id)), keyValues([['Knowledge', citation.knode_id], ['생성 작업', origin.origin_operation], ['최초 생성 Record', origin.origin_record_id], ['조회 시점 지원 Record', support.record_id]]));
  const derivations = [['최초 도출', origin], ...(support.records || []).filter(record => record.operation === 'k2k' && record.record_id !== origin.origin_record_id).map(record => [`지원 도출 · ${record.record_id}`, record.derivation])];
  for (const [title, derivation] of derivations) {
    const section = node('div', 'query-derivation');
    append(section, node('h3', '', title), tag(({ deductive: '연역', inductive: '귀납' })[derivation.inference_type] || derivation.inference_type), node('p', 'review-reason', derivation.derivation_basis));
    for (const [field, label] of [['assumptions', '가정'], ['limitations', '한계']]) {
      section.append(node('p', 'review-reason', `${label} · ${(derivation[field] || []).join('; ') || '기록 없음'}`));
    }
    for (const revision of derivation.premise_revision_ids || []) section.append(button(`도출 전제 ${revision}`, 'exact-link', () => openKnowledge(revision)));
    panel.append(section);
  }
  for (const record of support.records || []) if (record.data_versions?.length) {
    panel.append(node('h3', '', `조회 시점 자료 버전 · Record ${record.record_id}`));
    panel.append(versionList(record.data_versions));
  }
  if (citation.premise_revisions?.length) {
    panel.append(node('h3', '', '답변에 보존된 전제 내용'));
    for (const premise of citation.premise_revisions) {
      const row = node('div', 'query-premise');
      append(row, node('p', 'review-reason', premise.statement), button(`전제 Revision ${premise.node_revision_id}`, 'exact-link', () => openKnowledge(premise.node_revision_id))); panel.append(row);
    }
  }
  for (const [field, label] of [['direct_groundings', '직접 원문 근거'], ['transitive_source_refs', '전제를 통한 원문 계보']]) {
    if (!citation[field]?.length) continue;
    panel.append(node('h3', '', label));
    for (const evidence of citation[field]) {
      const row = node('div', 'query-lineage');
      row.append(node('code', 'revision-id', `KRevision ${evidence.node_revision_id} → I ${evidence.information_id} → Data ${evidence.data_id}`));
      if (evidence.source_execution_id) row.append(button('보존된 원문 위치 보기', 'evidence-link', () => openEvidence(evidence)));
      if (evidence.quote) row.append(node('pre', 'evidence-quote', evidence.quote));
      panel.append(row);
    }
  }
  for (const [field, label, basis] of [['direct_data_groundings', '직접 D2K 원문 근거', 'direct'], ['transitive_data_refs', '전제를 통한 D2K 원문 계보', 'transitive']]) {
    if (!citation[field]?.length) continue;
    panel.append(node('h3', '', label));
    for (const evidence of citation[field]) panel.append(queryDataCitation({ ...evidence, evidence_basis: basis }));
  }
  return panel;
}
function queryDataCitation(citation, number) {
  const panel = details(`${number ? 'D' + number + ' · ' : ''}D2K 등록 원문 · ${short(citation.data_id)}`, 'query-data-citation');
  const location = citation.locator;
  append(panel, button(`정확한 D2K 원문 근거 ${citation.grounding_id} 열기`, 'exact-link data-evidence-link', () => openDataEvidence(citation)),
    node('pre', 'evidence-quote', citation.quote || `원본 PDF ${location.page_index + 1}페이지에서 보존한 이미지`),
    keyValues([['Data', citation.data_id], ['근거 Record', citation.origin_record_id], ['View', citation.view_id],
      ['원본 위치', citation.representation === 'original_utf8_excerpt' ? `bytes [${location.byte_start}, ${location.byte_end}) · 줄 ${location.line_start}–${location.line_end}` : `${location.page_index + 1}페이지 · ${location.coordinate_system}`]]));
  return panel;
}
function renderQuery(data) {
  const { job, proposal, validation } = data;
  const accepted = data.accepted === true && job.state === 'answered';
  const dataSchema = proposal?.schema_version === 'wiki-query-answer-v3';
  const inferenceSchema = proposal?.schema_version === 'wiki-query-answer-v2' || dataSchema;
  setCrumb('질문 기록', accepted ? '검증된 답변' : '추가 확인 필요');
  const fragment = document.createDocumentFragment();
  append(fragment, button('‹ 질문 목록', 'back-button', showQueries), node('div', 'eyebrow', 'SAVED QUESTION'), node('h1', 'query-question', job.question), append(node('div', 'document-meta'), tag(queryStates[job.state] || job.state, accepted ? 'accepted' : 'held'), node('span', '', `Round ${job.round}`), node('span', 'meta-dot', '·'), node('span', '', '저장된 검토 기록')));
  if (accepted) {
    const paper = node('article', 'article-paper'); paper.style.marginTop = '24px';
    const hasInference = inferenceSchema && proposal.claims.some(claim => claim.knowledge_evidence?.length);
    append(paper, node('div', 'query-accepted', hasInference ? '✓ 독립 검증을 통과한 답변 · 원문과 승인된 추론을 구분합니다' : '✓ 독립 검증을 통과한 원문 기반 답변'));
    const counter = { value: 0 };
    let knowledgeNumber = 0;
    let dataNumber = 0;
    for (const claim of proposal?.claims || []) {
      const entry = node('div', 'article-item');
      if (inferenceSchema) entry.append(tag(({ direct_source: claim.data_evidence?.length ? 'D2K 원문 직접 근거' : '원문 직접 근거', accepted_system_inference: '승인된 시스템 K2K 추론', mixed_source_and_accepted_inference: '원문 + 승인된 시스템 K2K 추론' })[claim.epistemic_basis] || '근거 유형 미확인', claim.knowledge_evidence?.length ? 'inference' : ''));
      const text = node('p', 'article-text', claim.text);
      text.append(citationButtons([...(claim.evidence || []), ...(claim.source_evidence || [])], counter));
      entry.append(text);
      if (inferenceSchema) for (const citation of claim.knowledge_evidence || []) entry.append(queryKnowledgeCitation(citation, ++knowledgeNumber));
      if (dataSchema) for (const citation of claim.data_evidence || []) entry.append(queryDataCitation(citation, ++dataNumber));
      paper.append(entry);
    }
    fragment.append(paper);
  } else {
    const box = node('div', 'query-status-box');
    append(box, node('h2', '', '이 질문의 답변은 아직 확정되지 않았습니다'), node('p', '', validation?.reason || job.attention_reason || '추가 근거 확인 또는 검토가 필요합니다.'));
    fragment.append(box);
  }
  if (validation) {
    const review = details('검토 결과');
    review.append(node('p', '', validation.reason));
    for (const claim of validation.claims || []) {
      const card = node('div', 'round-card');
      const confirmed = ['supported', 'citations_sufficient', 'scope_preserved', 'no_new_inference', ...(inferenceSchema ? ['accepted_inference_faithful', 'inference_limits_preserved'] : [])].every(key => claim[key] === true);
      append(card, node('h3', '', claim.claim_key), tag(confirmed ? '근거 확인됨' : '검토 필요', confirmed ? 'accepted' : 'held'), node('p', '', claim.reason));
      if (inferenceSchema) card.append(node('p', '', `승인된 추론의 충실한 사용 · ${claim.accepted_inference_faithful === true ? '검증 통과' : '검토 필요'} / 추론 가정·한계 보존 · ${claim.inference_limits_preserved === true ? '검증 통과' : '검토 필요'}`));
      review.append(card);
    }
    fragment.append(review);
  }
  const rounds = details(`질문 진행 이력 · ${data.rounds?.length || 0} rounds`);
  for (const round of data.rounds || []) {
    const card = node('div', 'round-card');
    append(card, node('h3', '', `Round ${round.round ?? round.number ?? '—'}`));
    const roundState = round.state || round.status || round.proposal_status || round.proposal?.status;
    if (roundState) card.append(tag(roundState === 'answered' ? '답변 제안' : queryStates[roundState] || roundState));
    if (round.validation?.reason) card.append(node('p', '', round.validation.reason));
    const verdict = round.validation_verdict || round.verdict || round.validation?.verdict;
    if (verdict) card.append(tag(verdict === 'accepted' ? '해당 round 검증 통과' : '해당 round 검토 필요', verdict === 'accepted' ? 'accepted' : 'held'));
    for (const failure of round.failures || []) card.append(node('p', 'failure-note', typeof failure === 'string' ? failure : failure.reason || failure.error_code || failure.code || failure.error || '응답 구조 검증 실패 · 기록 보존됨'));
    if (round.attention?.reason) card.append(node('p', '', round.attention.reason));
    rounds.append(card);
  }
  fragment.append(rounds);
  const binding = details('질문과 출처 식별 정보');
  binding.append(keyValues([['Query', job.query_id], ['Import', job.import_id], ['Index', job.index_id], ['Context', job.context_sha256], ['읽기 범위', '저장된 실행·근거·검토 이력']]));
  for (const source of job.source_requests || []) binding.append(node('p', '', `원문 요청 · ${sourceName(source.data_id)} · ${(source.page_numbers || []).join(', ')}페이지: ${source.reason}`));
  fragment.append(binding);
  $('content').replaceChildren(fragment);
}
async function boot(reconnect = false) {
  if (typeof window.palimpsest.stores === 'function') return bootUnified(reconnect);
  $('reconnect').disabled = true;
  $('connection-label').textContent = '연결 확인 중'; $('connection-dot').className = 'status-dot';
  try {
    const connection = await (reconnect ? window.palimpsest.reconnect() : window.palimpsest.connection());
    if (!connection.connected && connection.error) throw new Error(connection.error);
    const [catalog, queries] = await Promise.allSettled([request('catalog'), request('queries')]);
    if (catalog.status === 'rejected') throw catalog.reason;
    $('connection-label').textContent = '로컬 저장소 연결됨'; $('connection-dot').className = 'status-dot connected';
    $('connection-label').title = `${connection.database || ''} · ${connection.version || ''}`;
    state.pages = catalog.value.pages;
    state.queries = queries.status === 'fulfilled' ? queries.value.queries : [];
    updateNavigation();
    if (state.mode === 'queries') showQueries();
    else if (state.mode === 'knowledge') await showKnowledge();
    else if (state.mode === 'reviews') await showReviews();
    else {
      const selected = state.pages.find((p) => p.page_id === state.page?.page_id) || state.pages.find((p) => p.kind === 'paper' && p.title.startsWith('Factors Produced by Macrophages')) || state.pages.find((p) => p.kind === 'paper') || state.pages[0];
      if (selected) await openPage(selected.page_id); else await showKnowledge();
    }
    if (queries.status === 'rejected') notice(`질문 기록을 읽지 못했습니다. ${errorText(queries.reason)}`);
    else if (queries.value.issues?.length) notice(`질문 기록 ${queries.value.issues.length}개의 무결성을 확인하지 못해 목록에서 제외했습니다.`);
  } catch (error) {
    $('connection-label').textContent = '연결 확인 필요'; $('connection-dot').className = 'status-dot failed';
    empty('로컬 저장소에 연결하지 못했습니다', errorText(error), () => boot(true));
  } finally { $('reconnect').disabled = false; }
}
$('wiki-nav').addEventListener('click', showWikiIndex);
$('data-nav').addEventListener('click', showData);
$('data-type').addEventListener('change', event => { state.dataFilter = event.target.value; showData(); });
$('realm-select').addEventListener('change', event => { state.realmId = event.target.value; refreshRealmView(); });
$('realm-manage').addEventListener('click', showRealmManager);
$('queries-nav').addEventListener('click', showQueries);
$('knowledge-nav').addEventListener('click', showKnowledge);
$('reviews-nav').addEventListener('click', showReviews);
$('search').addEventListener('input', (event) => { state.search = event.target.value; if (state.mode === 'data' && !state.dataId) showData(); else if (state.mode === 'wiki' && !state.page) showWikiIndex(); else if (state.mode === 'knowledge' && !state.nodeRevisionId) showKnowledge(true); else if (state.mode === 'reviews' && !state.reviewId) showReviews(true); else if (state.mode === 'queries' && !state.queryId) showQueries(); else renderLibrary(); });
$('close-assignment').addEventListener('click', closeAssignment);
$('realm-assignment').addEventListener('cancel', closeAssignment);
for (const filter of document.querySelectorAll('[data-filter]')) filter.addEventListener('click', () => { state.filter = filter.dataset.filter; for (const other of document.querySelectorAll('[data-filter]')) { other.classList.toggle('active', other === filter); other.setAttribute('aria-pressed', String(other === filter)); } if (state.mode === 'wiki' && !state.page) showWikiIndex(); else renderLibrary(); });
$('reconnect').addEventListener('click', () => boot(true));
$('close-source').addEventListener('click', closeSource);
$('information-tab').addEventListener('click', () => selectSourceTab('information'));
$('pdf-tab').addEventListener('click', () => selectSourceTab('pdf'));
$('pdf-previous').addEventListener('click', () => changePdfPage(state.pdfPage - 1));
$('pdf-next').addEventListener('click', () => changePdfPage(state.pdfPage + 1));
$('pdf-page').addEventListener('change', (event) => changePdfPage(Number(event.target.value)));
for (const [id, action] of [['pdf-zoom-out', (viewer) => viewer.setZoom(viewer.zoom - 0.25)], ['pdf-zoom-in', (viewer) => viewer.setZoom(viewer.zoom + 0.25)], ['pdf-rotate', (viewer) => viewer.rotate()]]) $(id).addEventListener('click', async () => { const ticket = state.sourceTicket; if (!pdfViewer) return; try { await action(pdfViewer); } catch (error) { if (ticket === state.sourceTicket) sourceStatus(errorText(error)); } });
document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeSource(); if (event.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) { event.preventDefault(); $('search').focus(); } });
boot();
