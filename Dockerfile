FROM python:3.12.14-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1
WORKDIR /opt/palimpsest
COPY requirements.lock pyproject.toml ./
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock
COPY src ./src
RUN python -m pip install --no-cache-dir --no-build-isolation --no-deps . \
    && groupadd --gid 10001 palimpsest \
    && useradd --uid 10001 --gid 10001 --no-create-home palimpsest
COPY tools/container_init.py tools/run_app_tests.py tools/check_storage_sql.py tools/run_d2i.py tools/run_pdf_evidence.py tools/run_d2k_pdf.py tools/run_propagation.py tools/desktop_bridge.py tools/realm_bridge.py ./tools/
COPY deploy/mineru-hybrid/run_parser.py ./deploy/mineru-hybrid/run_parser.py
COPY tests/app ./tests/app
COPY docs/schema/T02_storage_checks.sql ./tests/sql/T02_storage_checks.sql
USER 10001:10001
ENTRYPOINT ["palim"]
CMD ["--help"]
