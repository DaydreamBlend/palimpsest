# Local BGE-M3 worker

The optional worker uses `BAAI/bge-m3` revision
`5617a9f61b028005a4858fdac845db406aefb181`. It adds no ML dependency to the
headless Palimpsest application. The Docker image reuses the existing pinned
MinerU Hybrid ML runtime; the repository is mounted read-only at `/workspace`.
The image requires that retained base image to be present when building on a new
machine. Its underlying parser is not invoked.

## Build and model preparation

```powershell
docker build --pull=false -t palimpsest-retrieval-bge:0.1.0 deploy/retrieval
```

Existing local model directory:

```text
.local/models/bge-m3-5617a9f61b028005a4858fdac845db406aefb181
```

The seven required files total 2,295,415,758 bytes. The worker checks each file
against the pinned official LFS SHA-256 or Git blob hash before loading it and
records every SHA-256 in its result profile. It uses `local_files_only=True`,
`trust_remote_code=False`, and `weights_only=True` for the ColBERT state dict.
There is no automatic download or model fallback during inference.

To prepare that public revision in an empty/retryable local directory, use the
existing runtime's `hf` CLI; do not run a model-server download or use user sources:

```powershell
docker run --rm --env HF_HUB_OFFLINE=0 --env HF_HUB_DISABLE_IMPLICIT_TOKEN=1 --env HF_HUB_DISABLE_XET=1 --mount "type=bind,source=${PWD}/.local/models/bge-m3-5617a9f61b028005a4858fdac845db406aefb181,target=/models" --entrypoint hf palimpsest-mineru-hybrid:3.4.5-pro2605 download BAAI/bge-m3 --revision 5617a9f61b028005a4858fdac845db406aefb181 --local-dir /models --include config.json tokenizer.json tokenizer_config.json special_tokens_map.json sentencepiece.bpe.model pytorch_model.bin colbert_linear.pt --quiet
```

The destination directory must exist first. This command preserves other models.
No login or token is needed for these public files. On this Windows bind mount,
the HF downloader reported that it could not set temporary-file permissions;
the download completed and all seven final file hashes passed validation.

## Requests and execution

`tools/run_wiki_embeddings.py encode|rerank --input REQUEST --output RESULT
--model-path MODEL_DIRECTORY [--device cpu|cuda]` writes an exclusive new output
file atomically and prints only a compact result summary. Choose a new output
file for each attempt. The caller owns actual document IDs and provenance.

Encoding request:

```json
{"schema_version":"wiki-embedding-request-v1","documents":[{"document_id":"example","text":"Exact source text."}]}
```

Result: `wiki-embedding-result-v1`, canonical-JSON `input_sha256`, exact runtime
`profile`, and ordered documents containing `document_id`, `text_sha256`, and
`chunks`. Each chunk has `char_start`, `char_end`, `text_sha256`, and 1024 float32
values in `dense`. Unicode character offsets refer to the unchanged input text.

Dense chunks retain complete character coverage, including leading/trailing
whitespace. A fast tokenizer proposes at most 512-token windows with 64-token
overlap; each exact substring is tokenized again without truncation before
inference. Invalid/empty text or an unencodable boundary fails explicitly.

Rerank request:

```json
{"schema_version":"wiki-rerank-request-v1","query":"Question","passages":[{"chunk_id":"example:0","text":"Exact selected chunk."}],"profile":{"copy":"the complete encoding profile here"}}
```

The actual `profile` must equal the complete encoding result profile. Result:
`wiki-rerank-result-v1`, `input_sha256`, the same profile, and ordered
`scores:[{chunk_id,score}]`. Query or passage inputs over 512 tokens are rejected,
never truncated or silently split into a different scoring method. Supply
already-windowed passage text from the encoding result.

Example using the synthetic check directory:

```powershell
docker run --rm --gpus all --network none --mount "type=bind,source=${PWD},target=/workspace,readonly" --mount "type=bind,source=${PWD}/.local/models/bge-m3-5617a9f61b028005a4858fdac845db406aefb181,target=/models,readonly" --mount "type=bind,source=${PWD}/output/t07-retrieval-worker,target=/results" palimpsest-retrieval-bge:0.1.0 encode --input /results/encode-request.json --output /results/encode-result-new.json --model-path /models --device cuda
```

Use `rerank` and a rerank request for the second phase. For CPU, omit `--gpus all`
and select `--device cpu`; this deliberately creates a different runtime profile.

## Computation and verification

Dense retrieval uses the encoder's CLS vector with L2 normalization. Reranking
uses the same BGE-M3 encoder and its learned `colbert_linear.pt` head. CLS and
padding vectors are excluded, EOS is retained, and token vectors are normalized.
The score is the mean over query tokens of the maximum dot product against
passage tokens. There is no cross-encoder, sparse fusion, dense-score substitution
or probability interpretation. These operations follow the
[official BGE-M3 model card](https://huggingface.co/BAAI/bge-m3/tree/5617a9f61b028005a4858fdac845db406aefb181),
[FlagOpen M3 encoder](https://github.com/FlagOpen/FlagEmbedding/blob/master/FlagEmbedding/finetune/embedder/encoder_only/m3/modeling.py)
and [ColBERT scoring](https://github.com/FlagOpen/FlagEmbedding/blob/master/FlagEmbedding/inference/embedder/encoder_only/m3.py).

Pinned installed versions: torch 2.8.0, transformers 4.57.6, tokenizers 0.22.2,
safetensors 0.8.0, huggingface-hub 0.36.2. The code uses float32, eager attention,
deterministic Torch algorithms and disabled CUDA TF32. It does not promise bitwise
equivalence across devices, library builds or batch shapes; preserve the result
and its exact profile for historical reads. Any adapter change creates a new
`adapter_sha256` and consequently a new profile.

Pure app tests: `python -m unittest test_bge_retrieval` with `src` and `tests/app`
on `PYTHONPATH`. They use synthetic vectors/tokenizers and are not model-quality
measurements.

Actual GPU smoke results are in `output/t07-retrieval-worker/`: three synthetic
documents became 12 chunks; the 12,604-character mixed Korean/Greek document
became 10 windows reaching the exact final character. Maximum dense squared-L2
error was 9.63e-8. For the BMDC culture question, ColBERT scored the BMDC methods
passage 0.741466, the Korean BMDC passage 0.425486, and astronomy 0.295200. This
checks executable model behavior and basic relevance only; it is not a general
retrieval benchmark or proof that a returned claim is supported.
