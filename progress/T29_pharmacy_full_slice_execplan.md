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

## 2026-09-17 completed slice

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
- All 59 current K2W jobs passed independent GLM validation and committed 59
  Explanation W. Deterministic W2P composed them without another model call.
- A post-compose audit found one W whose two claim texts were punctuation-only
  placeholders. The shared K2W runtime now rejects claim text without any
  alphanumeric character, and the prompt states the same contract. Only that
  group was regenerated and independently revalidated. Its replacement W has
  four substantive Korean claims. The first P remains immutable audit history;
  the corrected presentation is P `01a0af4b-f2da-7465-9ca2-35514bed464e`,
  titled `약물치료학 (교정본)`.
- Final read-only store counts are D 1, I 77, current K 713, typed Edge 262,
  canonical W 60 (59 current composition inputs plus one replaced historical W),
  P 2, and P-W links 118. The corrected P contains 59 sections and 702 substantive
  Korean claims, and resolves back to the one registered source D.
- The local Electron registry now contains both the retained store and the T29
  store. A separate hidden packaged Electron instance connected 2/2 stores and
  rendered the corrected P with 59 sections, 702 claim cards, and zero renderer
  errors.
- The current P schema does not yet encode a formal supersedes/current pointer.
  Both P are visible in the catalog, while the retained correction receipt links
  their IDs. Formal P revision currentness remains follow-up work.

## Model usage

All figures below are provider-reported successful-call token counts. They do not
estimate tokens consumed by calls that failed before emitting a usable receipt.

| Phase | Calls | Input tokens | Output tokens | Average input/call | Average output/call |
|---|---:|---:|---:|---:|---:|
| I2K Generator | 37 | 514,522 | 489,668 | 13,906 | 13,234 |
| I2K Validator | 37 | 5,117,961 | 217,929 | 138,323 | 5,890 |
| Current K2W Generator | 59 | 604,065 | 179,772 | 10,238 | 3,047 |
| Current K2W Validator | 59 | 787,789 | 45,687 | 13,352 | 774 |

I2K used 5,632,483 input and 707,597 output tokens in total, equivalent to
152,229 input and 19,124 output tokens per source PDF page when divided by 37.
The Validator dominates I2K input because each independent review carries the
large frozen validation context. Current-composition K2W used 1,391,854 input and
225,459 output tokens. Preserved successful K2W attempts including superseded
repairs used 1,599,721 input and 276,705 output tokens; five failed receipts and
one cancelled long call have no complete token accounting.
