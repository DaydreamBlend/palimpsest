import * as pdfjs from './vendor/build/pdf.mjs';
pdfjs.GlobalWorkerOptions.workerSrc = new URL('./vendor/build/pdf.worker.mjs', import.meta.url).href;

export function regionRectangle(ref, baseWidth, baseHeight, width, height, rotation = 0) {
  const size = ref.page_size, box = ref.bbox;
  if (!Array.isArray(size) || size.length !== 2 || !Array.isArray(box) || box.length !== 4
      || [...size, ...box].some(value => !Number.isFinite(value)) || size.some(value => value <= 0)
      || box[2] <= box[0] || box[3] <= box[1] || Math.abs(size[0] / size[1] - baseWidth / baseHeight) > 0.012) return null;
  // Source boxes are retained top-left display-page coordinates, not PDF glyph boxes.
  const turn = ((rotation % 360) + 360) % 360;
  const points = [[box[0], box[1]], [box[2], box[1]], [box[2], box[3]], [box[0], box[3]]].map(([x, y]) => {
    const u = x / size[0], v = y / size[1];
    return turn === 90 ? [1 - v, u] : turn === 180 ? [1 - u, 1 - v] : turn === 270 ? [v, 1 - u] : [u, v];
  });
  const xs = points.map(p => p[0] * width), ys = points.map(p => p[1] * height);
  return { left: Math.min(...xs), top: Math.min(...ys), width: Math.max(...xs) - Math.min(...xs), height: Math.max(...ys) - Math.min(...ys) };
}

export class PdfPanel {
  constructor(container) {
    this.container = container; this.document = null; this.task = null; this.renderTask = null;
    this.regions = []; this.zoom = 1; this.rotation = 0; this.pageNumber = 1; this.pageCount = 0; this.serial = 0;
    this.resize = new ResizeObserver(entries => {
      const width = Math.round(entries[0].contentRect.width);
      if (width > 100 && width !== this.width) { this.width = width; if (this.document) this.renderPage(this.pageNumber).catch(() => {}); }
    });
    this.resize.observe(container);
  }
  async open({ base64, pageNumber = 1, regions = [], dataId }) {
    await this.clear();
    const serial = ++this.serial;
    this.container.textContent = '원본 PDF를 여는 중…';
    this.regions = regions; this.dataId = dataId; this.zoom = 1; this.rotation = 0;
    const binary = atob(base64), bytes = Uint8Array.from(binary, char => char.charCodeAt(0));
    this.task = pdfjs.getDocument({ data: bytes, isEvalSupported: false, useSystemFonts: false,
      cMapUrl: new URL('./vendor/cmaps/', import.meta.url).href, cMapPacked: true,
      standardFontDataUrl: new URL('./vendor/standard_fonts/', import.meta.url).href,
      wasmUrl: new URL('./vendor/wasm/', import.meta.url).href });
    this.task.onPassword = () => { this.task.destroy(); };
    const document = await this.task.promise;
    if (serial !== this.serial) { await document.destroy(); return { pageCount: 0 }; }
    this.document = document; this.pageCount = document.numPages;
    await this.renderPage(pageNumber);
    return { pageCount: this.pageCount, pageNumber: this.pageNumber, dataId };
  }
  async renderPage(number) {
    if (!this.document) return;
    if (!Number.isInteger(number) || number < 1 || number > this.pageCount) throw new Error('PDF 페이지 범위를 확인하세요.');
    this.pageNumber = number;
    const serial = ++this.serial;
    if (this.renderTask) { this.renderTask.cancel(); try { await this.renderTask.promise; } catch {} }
    const page = await this.document.getPage(number);
    if (serial !== this.serial) return;
    this.pageNumber = number;
    const base = page.getViewport({ scale: 1 });
    const rotated = page.getViewport({ scale: 1, rotation: (page.rotate + this.rotation) % 360 });
    const available = Math.max(280, (this.container.clientWidth || 650) - 36);
    const scale = (available / rotated.width) * this.zoom;
    const viewport = page.getViewport({ scale, rotation: (page.rotate + this.rotation) % 360 });
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const stage = document.createElement('div'); stage.className = 'pdf-stage';
    Object.assign(stage.style, { position: 'relative', width: `${viewport.width}px`, height: `${viewport.height}px`, background: 'white', margin: '16px auto', flex: '0 0 auto', boxShadow: '0 4px 24px #1f29371a' });
    const canvas = document.createElement('canvas'); canvas.dataset.pageNumber = String(number); canvas.setAttribute('aria-label', `원본 PDF ${number}페이지`);
    canvas.width = Math.ceil(viewport.width * dpr); canvas.height = Math.ceil(viewport.height * dpr);
    Object.assign(canvas.style, { width: `${viewport.width}px`, height: `${viewport.height}px`, display: 'block' });
    stage.append(canvas);
    const overlay = document.createElement('div'); overlay.className = 'pdf-overlay';
    Object.assign(overlay.style, { position: 'absolute', inset: '0', overflow: 'hidden', pointerEvents: 'none' });
    stage.append(overlay);
    let count = 0, unknown = 0;
    for (const ref of this.regions.filter(ref => ref.page_index === number - 1)) {
      // A nonstandard native page frame needs an explicit mapping; showing the
      // PDF is still valid, but guessing a crop/user-unit offset is not.
      if (page.view[0] !== 0 || page.view[1] !== 0 || page.userUnit !== 1 || page.rotate !== 0) { unknown++; continue; }
      const rect = regionRectangle(ref, base.width, base.height, viewport.width, viewport.height, this.rotation);
      if (!rect) { unknown++; continue; }
      const region = document.createElement('div'); region.className = 'pdf-region';
      region.dataset.blockId = ref.block_id || ''; region.title = '보존된 원문 블록 영역';
      Object.assign(region.style, { position: 'absolute', left: `${rect.left}px`, top: `${rect.top}px`, width: `${rect.width}px`, height: `${rect.height}px`, border: '2px solid #c2693e', background: '#e5a84a25', boxSizing: 'border-box' });
      overlay.append(region); count++;
    }
    const caption = document.createElement('p'); caption.className = 'pdf-caption';
    caption.textContent = `${number} / ${this.pageCount} 페이지${count ? ` · 원문 블록 ${count}개 강조` : ''}${unknown ? ' · 좌표계가 다른 영역은 강조 생략' : ''}`;
    Object.assign(caption.style, { textAlign: 'center', fontSize: '11px', color: '#77756f', padding: '0 12px 12px', margin: '0' });
    this.container.replaceChildren(stage, caption);
    this.renderTask = page.render({ canvasContext: canvas.getContext('2d'), viewport, transform: dpr === 1 ? null : [dpr, 0, 0, dpr, 0, 0] });
    try { await this.renderTask.promise; } catch (error) { if (error.name !== 'RenderingCancelledException') throw error; }
    this.container.dataset.pageNumber = String(number); this.container.dataset.pageCount = String(this.pageCount);
    return { pageNumber: number, pageCount: this.pageCount };
  }
  async setZoom(value) { this.zoom = Math.max(0.5, Math.min(2.5, value)); return this.renderPage(this.pageNumber); }
  async rotate() { this.rotation = (this.rotation + 90) % 360; return this.renderPage(this.pageNumber); }
  async clear() {
    ++this.serial;
    if (this.renderTask) { this.renderTask.cancel(); try { await this.renderTask.promise; } catch {} this.renderTask = null; }
    if (this.task) { try { await this.task.destroy(); } catch {} this.task = null; }
    this.document = null; this.pageCount = 0; this.container.replaceChildren();
  }
  destroy() { this.resize.disconnect(); return this.clear(); }
}
