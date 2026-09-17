# T27 batched I2K result

On 2026-09-15 Palimpsest changed large full-source I2K model delivery from one
monolithic request to deterministic, resumable batches. This changes no canonical
I and creates no K until all Generator batches are merged, independently validated,
and accepted by the existing KnowledgeRuntime transaction.

## Implemented

- `batched-i2k-delivery-v1` partitions the frozen source-review manifest in source
  and page order with limits of 8,000 source characters and three images.
- Every request binds the parent input digest, prompt/schema hashes, target IDs,
  Information IDs, media hashes, and the exact delivered character slices.
- Partial blocks cannot be cited as complete block evidence. Text/image anchors,
  citations, and Information-error requests must address content delivered to that
  batch.
- Generator candidate and review-item keys are deterministically namespaced during
  merge. The Validator sees the complete candidate catalog, audits the originating
  batches independently, and may return decisions in any order; merge restores the
  canonical candidate order.
- Runtime recomputes the full plan and every raw provider exchange before ordinary
  source-review normalization, staging, or decision can affect canonical storage.
  Generator and Validator provider response IDs must be disjoint.
- `tools/prepare_batched_i2k.py` prepares idempotent requests and merges only a
  complete response set. Existing successful response files are never overwritten.

## Pharmacy job

The existing I2K execution `01a0a425-a407-7e2d-9a0c-e72af9778064` keeps its
original 39 I and 112 source-review targets in Realm `약사`. Its generated plan is:

- 36 Generator batches
- 14,741-23,858 prompt characters per batch
- 1-3 attached images per batch
- plan SHA-256 `366ef463a74f5b6ec4b979caf974014afe0247057ac93a26e60523ce8cb60b02`

The first live local-GLM batch timed out at 1,200 seconds. A second attempt with a
3,600-second transport limit ran for 1,975.516 seconds and then returned
`local_glm_output_truncated`: the model exhausted its 65,536-token output limit.
Both failures are retained and no partial or false success was recorded. The user
then authorized GPT-5.6 Terra Medium as fallback. That provider uses a new frozen
I2K execution rather than changing the provider identity of the failed GLM job.

## Checks

- 2 focused batch/runtime checks: pass
- 37 existing source-review and selection checks: pass
- Environment: isolated PostgreSQL 18 / pgvector Compose project
- Live semantic result: none yet; GLM batch 1 produced two retained failures and
  no valid response

D2I grouping size was intentionally left unchanged for the next task.
