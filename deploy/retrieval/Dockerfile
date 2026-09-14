# Reuse the already verified local CUDA runtime, without touching app dependencies.
# Build context is deploy/retrieval. Mount the repository at /workspace read-only.
FROM palimpsest-mineru-hybrid:3.4.5-pro2605@sha256:3f9361035fa4d601d54ed524410d89871fe2524047b04a821594485aae93e0d4
RUN python -c "from importlib.metadata import version; expected={'torch':'2.8.0','transformers':'4.57.6','tokenizers':'0.22.2','safetensors':'0.8.0','huggingface-hub':'0.36.2'}; assert {p:version(p) for p in expected} == expected"
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
    TOKENIZERS_PARALLELISM=false CUBLAS_WORKSPACE_CONFIG=:4096:8 \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /workspace
ENTRYPOINT ["python", "/workspace/tools/run_wiki_embeddings.py"]
