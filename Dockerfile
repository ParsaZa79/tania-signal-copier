# =============================================================================
# Multi-stage Dockerfile for Tania Signal Copier
# =============================================================================
# Usage with Dokploy "Docker Build Stage":
#   - API service:       target stage "api"
#   - Dashboard service: target stage "dashboard"
#
# Docker context must be the repo root (.) so both api/ and bot/ are available.
# =============================================================================


# --------------- API Stage ---------------
FROM python:3.13-slim AS api

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy bot source (API imports models, mt5_adapter, executor from bot/)
COPY bot/src/ ./bot/src/
COPY bot/pyproject.toml ./bot/pyproject.toml

# Copy API source and install dependencies
COPY api/pyproject.toml api/uv.lock ./api/
WORKDIR /app/api
RUN uv sync --frozen --no-dev

COPY api/src/ ./src/

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]


# --------------- Dashboard Stage ---------------
FROM oven/bun:1 AS dashboard

WORKDIR /app
COPY dashboard/package.json dashboard/bun.lock ./
RUN bun install --frozen-lockfile
COPY dashboard/ .

# Next.js inlines NEXT_PUBLIC_* at build time.
ENV NEXT_PUBLIC_API_URL=https://api.kiaparsaprintingmoneymachine.cloud
ENV NEXT_PUBLIC_WS_URL=wss://api.kiaparsaprintingmoneymachine.cloud/ws
RUN bun run build

ENV NODE_ENV=production
EXPOSE 3000

CMD ["bun", "run", "start"]
