# T-Port API — production image
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# Dependencies first for layer caching.
COPY pyproject.toml ./
RUN mkdir app && touch app/__init__.py \
    && pip install ".[ai]" \
    && rm -rf app

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini docker-entrypoint.sh ./
RUN pip install --no-deps . \
    && chmod +x docker-entrypoint.sh \
    && useradd --system --uid 10001 --no-create-home tport
USER tport

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"
ENTRYPOINT ["./docker-entrypoint.sh"]
