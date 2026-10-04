# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/models XDG_CACHE_HOME=/tmp/.cache
WORKDIR /srv

COPY requirements.txt requirements-local.txt ./
RUN pip install -r requirements.txt
# Set INSTALL_LOCAL=true to bundle FinBERT (adds ~1 GB for CPU torch).
ARG INSTALL_LOCAL=false
RUN if [ "$INSTALL_LOCAL" = "true" ]; then pip install -r requirements-local.txt; fi

RUN useradd --create-home --uid 10001 app && mkdir -p /models && chown app /models
COPY app ./app
USER app

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2).status==200 else 1)"

# One worker: the job store is in-memory (see services/jobs.py).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
