FROM palimpsest-mineru:3.4.5@sha256:fdab78016483e1dbf0f416c9f74941a1242a91dae58fa2cc9617488ceb338854
COPY requirements-delta.lock /tmp/hybrid-requirements.lock
RUN python -m pip install --user --no-cache-dir --no-deps --require-hashes \
    --disable-pip-version-check -r /tmp/hybrid-requirements.lock
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 MINERU_MODEL_SOURCE=local MINERU_DEVICE_MODE=cuda
ENTRYPOINT ["mineru"]
