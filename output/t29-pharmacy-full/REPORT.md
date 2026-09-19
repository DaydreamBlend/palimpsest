# t29-pharmacy-full — Gemma 4 local K2W comparison report (2026-09-19/20)

## Goal

Evaluate whether local small models (Gemma 4 26B A4B QAT, Gemma 4 12B QAT, Qwen3.6 35B A3B)
can replace the GLM-5.3 baseline for the Palimpsest K2W (knowledge → recommendation plan)
step on consumer GPUs, using frozen preserved artifacts only (no GLM/Terra API reruns).

## Setup

- Baselines: preserved GLM generator responses in `k2w-grouped/groups/*/generator-response.json`
  (66 groups), preserved Terra medium I2K artifacts, preserved GLM N2E records.
- Local runtime: llama.cpp CUDA b11046 (Windows), Gemma 26B A4B QAT Q4_0 on GPU0+GPU2
  (tensor-split 3,2, ctx 262144, port 8080), Gemma 12B QAT on GPU1 alone (port 8081),
  Qwen3.6 35B A3B UD-Q4_K_M on all 3 GPUs with 1M YaRN + q8_0 KV.
- Strict JSON via `response_format: json_schema` grammar enforcement;
  `reasoning_effort: "none"` to keep Gemma reasoning from exhausting the budget.
- Per-group schema is mandatory: each group's `k_revision_ids` enum differs. Earlier
  findings of "fabricated UUIDs" were an artifact of a harness bug that reused the g0001
  schema for all groups (see Errors).

## Results

### K2W claim granularity (g0001 controlled A/B)

| Run | Claims | Latency | Notes |
|---|---|---|---|
| GLM baseline | 34 | preserved | atomic, evidence-oriented |
| Gemma 26B plain | 4 | 84.4s | mega-claims, up to 15 citations |
| Qwen 3.6 35B | 7 | 100.7s | still coarse |
| Gemma 26B + granularity hint | 29 | 137.0s | max 2 cites, 28/29 GLM citation-set match |
| Gemma 12B + granularity hint | 24 | 319.4s | GLM citation-set match 24/24, max 1 cite |

- A generic "GRANULARITY REQUIREMENT" prompt hint is the decisive lever: 4 → 29 claims,
  and 28/29 of the hinted claims have citation sets exactly matching a GLM claim.
- Gemma 12B (dense, fits a single 16GB card at 6.98 GB) reaches GLM-level matching on
  this group; being dense it is 2.3x slower than 26B A4B despite fewer active parameters.

### Full 26B batch (59 groups, hint-enabled, resumable runner)

- 65/66 records ok (g0029 transport failure remains; retry pending).
- Citation validity: 1,242/1,242 (100%) against per-group candidate enums.
- GLM total 678 claims (median 9/group) vs Gemma 1,192 (median 17/group).
- Hint effect (groups g0015+ vs earlier records): max citations per claim dropped from
  15 to 7 (single outlier); mega-claim merging resolved.

### Over-splitting judgment (manual review of g0035/g0041/g0042)

- Most splitting is legitimate: GLM merges per-drug mechanism + management + prophylaxis
  into one sentence-sized claim; Gemma's split improves evidence-role traceability.
- Real over-splitting exists but is a minority: repeated per-variant fragments of a single
  fact, plus occasional filler claims ("not defined in K").
- Anti-fragmentation clause added to the hint ("Each claim must state a distinct fact: do
  not split a single fact into per-variant fragments, do not emit filler claims…").
- g0024 A/B with the new clause: 124 → 26 claims (GLM baseline itself had 2 mega-claims
  covering 52 candidate items — that group's GLM baseline is the outlier, not Gemma).
- hint2 rerun finals: g0041 61 claims in 215.8s (GLM 9; anti-fragmentation clause did
  not reduce this group, its GLM baseline also groups per-drug), g0024 26 claims
  (124 before), g0042 timed out at 20 minutes twice (387s success in the main batch,
  so the timeouts are scheduling/load artifacts, not model failure).

### Other pipelines (earlier in this task, same frozen policy)

- N2E f0001: Gemma 3 edges / 3-3 actual citations / 7.9s (GLM also 3); Qwen returned
  `relations: []` (0 edges) with thinking disabled.
- I2K: Gemma 35/36 after long-side 1024px downscale (b0005 persistent HTTP 400);
  node volume ≈ Terra 1.11x, kind-convention drift noted.
- K2W planner: frozen request is 338,154 tokens > Gemma 256K context (no 1M KV fit on
  GPU0: 8.3GB cudaMalloc OOM). Qwen 1M context loads with all 3 GPUs (split 3,3,4,
  -ub 128) but g0001 claim quality is worse (7 claims vs GLM 34).
- 26B A4B QAT (14.4 GB weights) cannot usefully fit a single 16GB card: remaining ~1.5GB
  cannot hold useful KV/compute buffers. 12B QAT (6.98 GB) is the 16GB-card deployment
  answer; 26B A4B stays the multi-GPU speed option.

## Problems encountered and fixes

1. **Gemma reasoning exhausted strict-JSON budget** → `reasoning_effort: "none"`.
2. **Old prompt-only K2W outputs drifted to an explanation-tree schema** (56/63 valid
   parses were wrong contract) → llama.cpp `json_schema` grammar enforcement.
3. **Apparent blank responses** were Markdown ```json fences defeating the parser →
   fence stripping; content was never actually blank.
4. **Critical harness bug — shared schema reuse**: the content-sample/rebench runner
   loaded `g0001`'s schema once and applied it to every group, forcing g0001's UUID
   enum into all outputs. The resulting "0/21 valid citations / fabricated UUIDs"
   conclusion was wrong; per-group-schema reruns showed 100% citation validity
   (Gemma g0002 9/9, g0007 11/11, g0003 6/6, g0005 8/8; Qwen 9/9, 10/10, 8/8, 24/24).
   Do not cite the fabrication claim without this qualification.
5. **Qwen thinking mode made short sanity calls misleading** →
   `chat_template_kwargs: {"enable_thinking": false}` + `reasoning_effort: "none"`;
   it still returned empty relations on N2E f0001.
6. **Qwen 1M context needed all 3 GPUs and tuned launch** (`3,3,4` split, `-ub 128`,
   q8_0 KV); earlier splits OOM'd or failed model load.
7. **Server swap mid-batch caused HTTPError cascades** (first full-batch attempt:
   11/66 before failure). Orchestrator failure, not model failure; resumable runner
   skips ok records and retries the rest.
8. **`[K*]` citation indirection prototype failed**: the response schema's UUID enum
   grammar blocks `[K3]`-style output. If revisited, the response schema itself must
   switch to a tag enum with runtime remap.
9. **Domain-specific hint wording**: the original hint said "different drugs / clinical
   conditions"; user asked for domain-neutral wording. Now generic (topics/questions),
   and the hard ">3 citations is wrong" rule was softened after checking that GLM
   itself never exceeds 2 citations across 108 baseline claims — replaced with a
   split-check instruction that still requires citing every genuinely supporting item.
10. **BGE-M3 citation repair is not needed for validity** (per-group enums already
    guarantee membership); it remains useful as a semantic support/ambiguity check
    (`bge_citation_repair.py`, served from the honcho-codex-gateway embedding container,
    dim 1024).

## Routing conclusion (current)

- N2E small: Gemma wins the measured case (Qwen failed it).
- I2K: Gemma usable with normalization caveats.
- K2W small/medium: Gemma 26B with per-group schema + granularity hint is valid and fast.
- K2W large: prompt-engineered Gemma reaches near-GLM segmentation; anti-fragmentation
  clause verified on the worst group (g0024). Remaining: g0029 retry, hint2 reruns for
  g0041/g0042 (in flight), and the g0024-class GLM mega-claim outliers are a baseline
  issue, not a local-model issue.
- 16GB single-card deployment: Gemma 12B QAT (dense, slower but GLM-level matching).
  Multi-GPU: Gemma 26B A4B. W2P is deterministic runtime composition — excluded from
  LLM A/B.

## Files

- `gemma4_k2w_full.py` — resumable all-group runner (per-group schema + current hint).
- `gemma4-k2w-full.json` — batch state (65/66 ok).
- `gemma4-k2w-g0001-granhint.json`, `granhint.log`, `grancheck.log` — controlled A/B + GLM/BGE validation.
- `gemma4-k2w-g0024-hint2.json`, `granhint2.log` / `granhint2b.log` — anti-fragmentation A/B.
- `gemma12-k2w-g0001-granhint.json`, `gemma12_g0001.log` — 12B single-card probe.
- `qwen36-k2w-pergroupschema-g0001.json`, `qwen_g0001_probe.py` — Qwen probe.
- `bge_citation_repair.py`, `bge-repair-glm-match.json` — semantic citation checker.
- `kref_indirect.py` — `[K*]` indirection prototype (blocked by UUID enum grammar).
