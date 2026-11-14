# EvolvXSI core API (FastAPI). Lite mode needs no search index and no model server.
# Build from this directory:  docker build -t evolvxsi-core .
# Every dependency is a prebuilt wheel, so no system packages are installed.
FROM python:3.13-slim AS build
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PROJECT_ENVIRONMENT=/opt/venv
RUN pip install --no-cache-dir uv==0.9.5
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --group backend

FROM python:3.13-slim
RUN useradd --create-home --uid 10001 evolvxsi
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY --chown=evolvxsi:evolvxsi . .
ENV PATH=/opt/venv/bin:$PATH PYTHONPATH=/app PYTHONUNBUFFERED=1
USER evolvxsi
# Tokenizers baked into the image, so token counting works with no outbound internet. The default tokenizer
# (chat token counting and the fallback) loads without a revision; the default embedding model's tokenizer loads
# at the revision pinned in shared_configs/embedding_models.py, so the two must match
# (tests/unit/model_server/test_dockerfile_bundled_model.py checks it).
RUN HF_HUB_DISABLE_XET=1 python -c "from tokenizers import Tokenizer; \
Tokenizer.from_pretrained('nomic-ai/nomic-embed-text-v1')"
RUN HF_HUB_DISABLE_XET=1 python -c "from tokenizers import Tokenizer; \
Tokenizer.from_pretrained('ibm-granite/granite-embedding-97m-multilingual-r2', revision='835ad14087e140460703cf0fae09f97d469d65c2')"
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=4).status == 200 else 1)"
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn evolvxsi.main:app --host 0.0.0.0 --port 8080"]
