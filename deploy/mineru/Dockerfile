FROM python:3.12.14-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/mineru
RUN python -m pip install --no-cache-dir --report /opt/mineru/install-report.json \
    'torch==2.8.0' 'torchvision==0.23.0' \
    'mineru[pipeline] @ https://files.pythonhosted.org/packages/94/a6/d60b161482cdcc2a4a8d01994320c55b5f804e26fda07845440a9d3080a8/mineru-3.4.5-py3-none-any.whl#sha256=4a73b865920bb9109c1b8b1bc46567e296bf0133a67106a04effd219536ae72d'
COPY runtime-fixes.lock ./
RUN python -m pip install --no-cache-dir --require-hashes --report /opt/mineru/runtime-fixes-report.json -r runtime-fixes.lock
RUN python -m pip freeze --all > /opt/mineru/resolved-requirements.txt \
    && groupadd --gid 10001 mineru && useradd --uid 10001 --gid 10001 --create-home mineru
USER 10001:10001
ENTRYPOINT ["mineru"]
