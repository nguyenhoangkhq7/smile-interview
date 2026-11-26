FROM python:3.14-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface

RUN apt-get update \
 && apt-get install -y --no-install-recommends --only-upgrade libzstd1 \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 1001 appgroup \
 && useradd --system --uid 1001 --gid appgroup --create-home appuser \
 && mkdir -p /app/.cache/huggingface \
 && chown -R appuser:appgroup /app

COPY requirements-docker.lock .
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --require-hashes --only-binary=:all: -r requirements-docker.lock \
 && python -m pip check \
 && python -m pip uninstall --yes pip

COPY --chown=appuser:appgroup . .

# Keep the shared key directory owned by the backend's runtime UID.
RUN install -d -o appuser -g appgroup -m 0700 /run/smile-ai
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
