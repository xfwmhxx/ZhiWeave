FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

RUN pip install --no-cache-dir uv==0.12.7

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 zhiweave \
    && mkdir -p /data/models /data/uploads \
    && chown -R zhiweave:zhiweave /app /data
USER zhiweave

EXPOSE 8000
CMD ["uvicorn", "studyrag_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
