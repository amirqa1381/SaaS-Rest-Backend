# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

# uv installed via the official static binary (no pip bootstrap needed)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# Install dependencies first (separate layer -> cached unless pyproject/lock change)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Now copy the actual source (manage.py lives inside src/)
COPY src ./src

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src

WORKDIR /app/src

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
