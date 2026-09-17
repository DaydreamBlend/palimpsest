# T27 — resumable batched I2K delivery

Status: implemented and isolated-PG verified on 2026-09-15; the live pharmacy
job has a 36-batch Generator plan and no completed model batch yet.

Status: implemented and isolated-PG verified on 2026-09-15; the live pharmacy
job has a 36-batch Generator plan and no completed model batch yet.

## Outcome

Replace the single large provider exchange for full-source I2K with deterministic,
resumable batches. Canonical I, the frozen source snapshot, Realm scope, semantic
selection policy, independent validation, and the final atomic K commit remain
unchanged.

## Relevant contract and code

- `docs/interfaces/SOURCE_REVIEW.md`
- `docs/decisions/I2K_SOURCE_ONLY_K2K_INFERENCE.md`
- `src/palimpsest/knowledge_runtime.py`
- `src/palimpsest/knowledge_requests.py`
- `src/palimpsest/source_review.py`
- `tools/run_knowledge_model.py`

## Steps

1. Deterministically partition the frozen source-review targets by source/page,
   bounded source characters, and owned media. A batch may slice model delivery,
   but never creates or edits I.
2. Produce strict Generator requests per batch and merge only their schema-bound
   responses. Namespace candidate/item keys and prove complete target, I-range,
   and media coverage.
3. Produce independent Validator requests over the same source batches, with the
   complete candidate catalog available for duplicate decisions, then merge the
   exhaustive decisions.
4. Teach KnowledgeRuntime to verify the aggregate batch receipt, every provider
   response, the deterministic plan, and the exact merged response before staging
   or deciding.
5. Add one focused pure test and one Runtime integration check. Run the pharmacy
   PDF through batched I2K, then continue N2E/K2K only after validated K commits.

## Boundaries

- No D2I rerun, D fetch, D2K, cross-Realm input, W/P work, or source mutation.
- Partial batches are durable execution evidence but have no canonical K effect.
- A missing, changed, or duplicated batch keeps the execution unfinished.
- The cancelled monolithic retry and its earlier timeout remain preserved.

## Verification result

- The final plan covers all 39 I, 112 frozen review targets, every retained text
  range, and all 75 media assets in 36 resumable Generator calls.
- Request size is 14,741-23,858 characters with 1-3 images per call.
- Two batch/runtime checks and 37 existing source-review/selection checks pass in
  isolated PostgreSQL 18 + pgvector.
- GLM batch 1 timed out at 1,200 seconds, then exhausted its 65,536-token output
  limit after 1,975.516 seconds with a 3,600-second transport limit. Both failure
  receipts remain; the user authorized a new Terra Medium execution as fallback.

## Verification result

- The final plan covers all 39 I, 112 frozen review targets, every retained text
  range, and all 75 media assets in 36 resumable Generator calls.
- Request size is 14,741-23,858 characters with 1-3 images per call.
- Two batch/runtime checks and 37 existing source-review/selection checks pass in
  isolated PostgreSQL 18 + pgvector.
- A first live batch was stopped after ten minutes without a response. No success
  or failure receipt was written, so the durable resume point remains batch 1.
