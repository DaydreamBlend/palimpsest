# T29 pharmacy full slice

Outcome: build a fresh PostgreSQL 18/pgvector store for `test_input/약물치료학.pdf`,
register it in Realm `약사`, and produce one reviewable D→I→K→E/K2K→Explanation
W→P slice using the local GB10 GLM endpoint. The existing pharmacy database and
its 448 English K revisions remain unchanged.

## Implementation

1. Fix source-only Electron stores so the global K catalog and exact K reader do
   not require a legacy Wiki projection.
2. Add `source-groups-v2`. It preserves the v1 heading groups, but deterministically
   splits titleless groups at every page and bounds other oversized groups by page
   and 12,000 source characters. It preserves every block and exact content range.
3. Preserve the cited source language in I2K and K2K, and the query/K language in
   K2W. Generator and independent Validator remain separate structured calls.
4. Use the Windows RTX 5080 (`GPU-ae1e4ffa-2dba-7ba3-f9f7-1bae0ab26f57`, PCIe
   width x16) for MinerU. The observed 4060 Ti links are x2/x4 and are not selected.
5. Start a new isolated Compose project and DB, migrate it, register the PDF with
   Realm membership, run MinerU image200/Pro high D2I, and verify full D↔I coverage.
6. Run batched I2K, N2E, K2K, model-planned grouped Explanation K2W, and
   deterministic W2P through `http://172.30.1.11:8888/v1` model
   `glm-5.3-flash-nvidia-nvfp4`.
7. Point the unified Electron store catalog at the completed new store alongside
   any retained stores, package the current renderer, and verify in a hidden UI.

## Boundaries and evidence

- D2I has zero application-LLM calls. Parser/model/profile hashes, source bytes,
  page images, grouped I, Records, receipts and exact IDs remain preserved.
- Model calls begin at I2K. Existing K is neither translated nor overwritten.
- Partial/failed semantic work is retained as such; token, time or count limits do
  not turn it into completion.
- The task report records I sizes, model token usage, accepted/held counts, relation
  results, W/P IDs, tests and any remaining limitations.

## 2026-09-17 checkpoint

- D2I completed 37/37 pages with native PDF extraction plus 200 DPI image OCR.
- I2K accepted 712 Korean K; N2E committed 262 typed relation revisions; K2K
  committed one inferred K with exact premises, for 713 current K total.
- BGE-M3 embedded 712 documents as 736 chunks. Semantic grouping used the K
  meanings, typed edges, and BGE neighbors as hints; it did not hardcode this
  document's page ranges or disease names.
- The local GLM proposed 51 K2W groups. Independent validation rejected a mixed
  pneumonia/tuberculosis group; a targeted repair produced nine replacement
  groups. The final 59-group plan covers every current K exactly once and passed
  the retained and targeted independent validations.
- Fifty-nine K2W executions are prepared, but no W or P has been committed. The
  first grouped Generator attempt exposed a vLLM structured-output compatibility
  failure and was stopped after two failed calls. Resume only after fixing that
  shared schema boundary; do not treat the prepared jobs as completed work.
