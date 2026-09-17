# Current model provider

From 2026-09-15, every active Palimpsest Generator and Validator call uses the user's local OpenAI-compatible server:

- Base URL: `http://172.30.1.11:8888/v1`
- Model: `glm-5.3-flash-nvidia-nvfp4`
- Context window: `1048576`
- Temperature / seed: `0` / `0`
- Maximum output tokens: `262144`
- Thinking: disabled for strict extraction/validation calls; the full output ceiling remains available to the structured result
- Authentication: none

`tools/run_knowledge_model.py` is the single host call path. It sends strict JSON Schema requests, carries I images as data URLs, records the server response ID as the independent provider reference, and preserves token usage. Historical Terra/Codex OAuth receipts and dated reports remain historical evidence; they are not rewritten.

Resumable batch delivery uses `tools/run_knowledge_batches.py` with four concurrent
requests. This matches the measured C4 admission point; C6 queued two requests.

The endpoint has passed model-list, strict JSON Schema, and real 200 DPI PDF page-image smoke checks. Generator and Validator still run as separate requests with separate provider response IDs.

`palim knowledge prepare --provider codex-terra` freezes the existing OAuth-backed
GPT-5.6 Terra Medium profile for a new execution. `tools/run_knowledge_model.py
--provider codex-terra` performs that execution through the isolated Codex provider.
A provider change always creates a new execution; it never rewrites a prepared job
or mixes receipts from different providers.

Large full-source I2K jobs use `batched-i2k-delivery-v1`. The frozen source-review
manifest is partitioned deterministically by source order, page, text range, and
media count. `tools/prepare_batched_i2k.py` writes resumable strict-schema calls
and merges them only after every range, media asset, Information, and review target
is covered. Partial blocks cannot be cited as whole-block evidence. The Runtime
recomputes the plan and every exchange before the ordinary source-review stage or
decision path can affect canonical K. Generator and Validator batch response IDs
must remain disjoint.
