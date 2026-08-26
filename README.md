# SaaS API Metering & Billing Platform

A usage-based metering and billing engine, built the way SaaS billing
tools like Stripe Billing or Chargebee are shaped internally: usage events
come in through an API, get rated against per-event pricing rules, and are
periodically rolled up into invoices which are then charged and reconciled
against a payment provider (Stripe) — automatically, on a schedule, with
webhooks and reconciliation both feeding the same state machine so nothing
depends on a single source of truth staying available.

This is a learning/portfolio project. It's built with the architecture
discipline of a production system, but hasn't been hardened for one yet —
see [Roadmap](#roadmap--known-limitations) for exactly where that line
currently sits.

## What it does

- **Meter usage** — clients send usage events (API calls, storage, seats,
  whatever an `event_type` represents) via an API-key-authenticated
  endpoint. Ingestion is idempotent per client.
- **Price it** — each event type has a per-unit price. Usage is rated
  against that price when invoices are generated.
- **Bill on a schedule** — a Celery Beat job checks nightly which projects
  are due for billing (based on each project's own `billing_frequency` and
  `next_billing_date`) and generates invoices for exactly the usage in
  that period — not an arbitrary caller-supplied range.
- **Charge and track** — invoices can be paid via Stripe (payment
  intents), retried on failure, and refunded (full or partial).
- **Stay in sync with the provider** — Stripe webhooks update payment/
  refund state in near-real-time; a separate reconciliation job polls
  Stripe directly every few minutes as a fallback for any webhook that
  never arrived. Both paths converge on the same state machine, so it
  doesn't matter which one gets there first.

## Architecture

Three layers, applied consistently across every resource:

```
route  → validates the request, resolves the authenticated user/client
service → business logic, guards, orchestration
repository → the only layer that talks to the ORM/DB directly
```

A few decisions that shaped the rest of the system:

- **Every domain object with meaningful state (`Invoice`, `Payment`,
  `Refund`) is a finite state machine**, not a free-form status string.
  Each has an explicit allowed-transitions map; illegal transitions raise,
  and transitioning to the current status is a no-op rather than an
  error. This is what makes webhook redelivery and reconciliation safe to
  run repeatedly against the same row.
- **Billing is worker-driven, not request-driven.** There's no endpoint
  that accepts an arbitrary `period_start`/`period_end` — invoicing is
  always anchored to a project's own `next_billing_date`, and that date
  only advances after the invoice is actually created (both happen in one
  transaction). This avoids the double-invoicing risk that comes with
  letting a caller specify billing periods directly.
- **Webhook processing is idempotent and redelivery-safe.** Every
  processed Stripe event is recorded by `event_id`; a duplicate delivery
  short-circuits before any handler runs. Just as importantly, an event
  type or status the app doesn't yet recognize is *not* marked processed
  — so Stripe keeps redelivering it until the code that handles it ships,
  instead of it disappearing silently.
- **Tenant isolation is enforced at the repository layer, not the route
  layer.** Every "fetch by external_id" method joins through to
  `Project.user_id` (directly, or transitively through client/invoice/
  payment), so there's one consistent place the ownership check lives
  rather than a check repeated ad hoc in every route.
- **Public-facing IDs are opaque external IDs**, not database primary
  keys — internal integer IDs never leave the service layer.

## Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI |
| ORM / DB | SQLAlchemy + PostgreSQL |
| Migrations | Alembic |
| Background jobs / scheduling | Celery + Celery Beat |
| Job broker / lock | Redis |
| Payments | Stripe (payment intents, refunds, webhooks) |
| Auth | JWT access tokens + refresh tokens |
| Admin panel | SQLAdmin |
| Testing | pytest, against a real Postgres test database |

## Project structure

```
app/
├── api/routes/        # HTTP layer — one router per resource
├── services/           # business logic, guards, orchestration
├── repositories/        # ORM queries, ownership scoping
├── models/              # SQLAlchemy models
├── schemas/              # Pydantic request/response models
├── payment/               # Stripe-specific service/repository/status logic
├── providers/              # payment provider implementations
├── tasks/                    # Celery tasks (billing, usage ingestion, reconciliation)
└── core/                      # config, DB session, security, Celery app

tests/                          # pytest suite — see docs/TESTING.md
docs/
└── TESTING.md                  # what's tested and why
```

## Getting started

### Prerequisites

- Python 3.12+
- PostgreSQL
- Redis (for Celery)
- A Stripe account (test mode is fine) for `stripe_secret_key` /
  `stripe_webhook_secret`

### Setup

```bash
git clone <repo-url>
cd <repo>
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/saas_db
SECRET_KEY=<a long random string>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
REDIS_URL=redis://localhost:6379/0
```

Run migrations:

```bash
alembic upgrade head
```

Start the API:

```bash
uvicorn app.main:app --reload
```

Start a worker and the beat scheduler (separate terminals):

```bash
celery -A app.core.celery_app worker --loglevel=info
celery -A app.core.celery_app beat --loglevel=info
```

### Running tests

The test suite runs against a **real Postgres instance**, not mocks or
SQLite — this is deliberate, since a lot of what's being tested
(unique constraints, `SELECT ... FOR UPDATE` locking, transaction
rollback behavior) doesn't reliably reproduce outside real Postgres.

```bash
docker run -d --name saas-test-db \
  -e POSTGRES_USER=saas_user \
  -e POSTGRES_PASSWORD=saas_password \
  -e POSTGRES_DB=saas_db_test \
  -p 5433:5432 postgres:16

pytest -v
```

Each test creates and tears down its own schema, so tests don't leak
state between runs. See [`docs/TESTING.md`](docs/TESTING.md) for what's
covered and why — coverage is intentionally concentrated on billing
correctness, payment/refund state, tenant isolation, and webhook/
reconciliation resilience rather than spread evenly across every CRUD
endpoint.

## API overview

| Group | Purpose |
|---|---|
| `/auth` | register, login, token refresh |
| `/projects` | a billable unit — owns clients, billing frequency, next billing date |
| `/clients` | who's being billed within a project |
| `/event_types` | what's metered (e.g. `api_call`, `storage_gb`) |
| `/pricing_rules` | per-unit price for an event type |
| `/api-keys` | client-scoped keys used to authenticate usage ingestion |
| `/usage-events` | ingest metered usage (API-key auth, idempotent per client) |
| `/invoices` | generated automatically; read-only from the API |
| `/payments` | charge an invoice, retry a failed payment |
| `/payments/{id}/refunds` | full or partial refunds |
| `/webhooks/stripe` | Stripe webhook receiver (signature-verified) |
| `/dashboard` | account-level summary |

All resource routes are scoped to the authenticated user's own data;
usage ingestion is scoped to the API key's client.

## Roadmap / known limitations

Being upfront about where this currently falls short of
production-ready, roughly in the order I'm planning to address them:

- **CI** — not wired up yet; in progress.
- **Rate limiting, API versioning, and a consistent error response
  envelope** — not implemented.
- **Money is `float` in places** in application code despite the
  database columns correctly being `Numeric` — works today, but `Decimal`
  end-to-end would remove a class of precision bugs before they happen.
- **The usage-ingestion worker's duplicate-detection is broader than it
  should be** — it currently treats *any* database integrity violation as
  a harmless duplicate event, not just the specific unique-constraint
  case it's meant to catch, which could mask a genuine data problem
  (e.g. a stale foreign key) as if it were routine. Documented with a
  test in `docs/TESTING.md`.
- **No idempotency-key protection on some client-facing mutation
  endpoints** (e.g. double-submitting a payment charge) — webhook
  idempotency is solid; the request-side equivalent isn't there yet
  everywhere.