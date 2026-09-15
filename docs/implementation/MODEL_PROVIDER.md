# Current model provider

From 2026-09-15, every active Palimpsest Generator and Validator call uses the user's local OpenAI-compatible server:

- Base URL: `http://172.30.1.11:8888/v1`
- Model: `glm-5.3-flash-nvidia-nvfp4`
- Context window: `700160`
- Temperature / seed: `0` / `0`
- Maximum output tokens: `65536`
- Authentication: none

`tools/run_knowledge_model.py` is the single host call path. It sends strict JSON Schema requests, carries I images as data URLs, records the server response ID as the independent provider reference, and preserves token usage. Historical Terra/Codex OAuth receipts and dated reports remain historical evidence; they are not rewritten.

The endpoint has passed model-list, strict JSON Schema, and real 200 DPI PDF page-image smoke checks. Generator and Validator still run as separate requests with separate provider response IDs.
