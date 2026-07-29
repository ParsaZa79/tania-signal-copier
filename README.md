# Signal Copier

Beginner-first MT5 copy trading with a Next.js dashboard and FastAPI execution API.

## What is included

- `dashboard/` — trader discovery, guided paper/live setup, risk explanations, account setup, and portfolio monitoring.
- `api/` — account-scoped copy APIs, PostgreSQL models, durable outbox worker, audit history, and neutral MT5 order primitives.
- `mt5/` and `silicon-metatrader5/` — local MT5 bridge images for Linux and Apple Silicon development.

Telegram ingestion and the former bot runtime have been retired. Production copy sources are connected MT5 accounts only.

## Local development

Run PostgreSQL and one MT5 bridge, then start the services:

```bash
cd api
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
cd dashboard
bun install --frozen-lockfile
bun run dev
```

Open `http://localhost:3000/copy-trading` and API docs at `http://localhost:8000/docs`.

For a frontend-only marketplace preview with realistic data:

```bash
cd dashboard
NEXT_PUBLIC_COPY_TRADING_PREVIEW=true bun run dev
```

Then open `http://localhost:3000/copy-trading?preview=1`.

## Live-copying safety

Live copying fails closed. `PAPER_LIVE_ENABLED` is `false` by default and the country eligibility table starts empty. Enabling live access also requires a healthy isolated account runtime, an approved country and disclosure version, account membership, the safety checklist, and any market-overlap acknowledgement.

The public API never receives Docker access or raw MT5 credentials. Live orders are sent through `COPY_RUNTIME_MANAGER_URL` to one isolated runtime per connected account. That control-plane service is deployed separately and is intentionally not part of this paper-first release; keep live copying disabled until it has been provisioned and verified.

## Production requirements

- PostgreSQL reachable through `DATABASE_URL`; the API image runs Alembic before startup.
- A persistent `/app/data` mount for encrypted account configuration, legacy archive input, and compatibility history.
- An ordered `MT5_RUNTIME_ENDPOINTS` pool of private RPyC endpoints. The API persists a
  unique endpoint assignment for every configured account and fails closed when the
  pool is full; it never moves another account or shuts down another terminal.
- `PAPER_LIVE_ENABLED=false` until the runtime manager and an approved jurisdiction policy are both present.
- Public liveness at `/api/health/` and deployment readiness at `/api/health/ready`.

## Verification

```bash
cd api
TEST_DATABASE_URL=postgresql+asyncpg://... uv run pytest
uv run ruff check .
uv run pyright
```

```bash
cd dashboard
bun run lint
TEST_DATABASE_URL=postgresql://... bun run test
bun run build
```

See `api/README.md` and `dashboard/README.md` for service-specific configuration.
