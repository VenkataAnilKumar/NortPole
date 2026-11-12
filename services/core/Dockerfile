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
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=4).status == 200 else 1)"
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn evolvxsi.main:app --host 0.0.0.0 --port 8080"]
