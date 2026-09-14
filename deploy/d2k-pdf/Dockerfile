# Optional source-view runtime. Reuses the existing locally verified renderer
# layers; rendering/re-verification never invokes MinerU or its model.
FROM palimpsest-mineru-hybrid:3.4.5-pro2605
USER root
WORKDIR /opt/palimpsest
COPY requirements.lock pyproject.toml ./
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock
COPY src ./src
RUN python -m pip install --no-cache-dir --no-build-isolation --no-deps .
COPY tests/app ./tests/app
ENV PYTHONPATH=/opt/palimpsest/src PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1
USER 10001:10001
ENTRYPOINT ["python", "-m", "palimpsest"]
CMD ["--help"]
