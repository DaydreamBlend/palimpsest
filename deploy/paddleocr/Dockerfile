# Existing local CUDA base; verify its image ID against runtime-profile before building.
FROM palimpsest-mineru:3.4.5@sha256:fdab78016483e1dbf0f416c9f74941a1242a91dae58fa2cc9617488ceb338854
COPY requirements-delta.lock /tmp/paddle-requirements.lock
RUN python -m pip install --user --no-cache-dir --no-deps --require-hashes \
    --disable-pip-version-check -r /tmp/paddle-requirements.lock
ENV PATH="/home/mineru/.local/bin:${PATH}" \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
COPY run_parser.py /opt/paddleocr/run_parser.py
ENTRYPOINT ["python", "/opt/paddleocr/run_parser.py"]
