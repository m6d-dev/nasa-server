# CLAUDE.md

Vigil backend (NASA Space Apps 2026). What the server must do is in
[BACKEND_TZ.md](BACKEND_TZ.md); the project plan is [PLAN.md](PLAN.md).
The layering follows the Anbor CRM v2 (`crm-ecommerce-backend/src/app`),
trimmed to what a one-process hackathon server needs.

## Layout

```
src/vigil_types/          contract package (the CRM's anbor_types): frame codec,
                          commands, queries, DTOs. Never imports src.app.
src/app/
  api/                    Litestar controllers + /ingest, /live websockets. Thin:
                          bind input → mediator → DTO.
  application/<boundary>/ handlers (one per message), services, ports (Protocols)
  domain/monitoring/      the pipeline: aggregation, context, norm, levels,
                          incident. Pure, no I/O. ML imports it offline.
  domain/narration/       template text and the LLM-answer acceptance rule
  data_access/orm/        SQLAlchemy models (mirror sql/schema.sql), repositories,
                          unit of work, db_scope
  data_access/sql/schema.sql  the ONLY schema authority; applied at start if absent
  infra/di/               dependency-injector containers, root_di wires them
  infra/cqrs/             message ↔ handler registration, policy on every line
  infra/event_sourcing/   domain events → persistence, /live, LLM, reports
  infra/impls/            event bus, live hub, Ollama/vdev clients, model files
  shared_kernel/          Result, errors, config, ports shared by all
src/bootstrap.py          DI + CQRS + subscriptions, start-up restore
src/config/asgi.py        the Litestar app
```

Boundaries: `monitoring` (frames, minutes, norm, levels, alerts — has a domain),
`narration` (has a domain), `crew` (crew, check-in), `reporting`, `radiation`,
`simulation` (proxy to vdev). Cross a boundary with a query, an event, or a port
declared by the consumer and bound in DI — never by importing another
boundary's repository.

## Rules carried over from the CRM

- **Everything has a declared format.** `str` fields carry `max_length` and,
  where there is a shape, a regex. Validation lives in `vigil_types`.
- **Expected failure is `Result.err`**, not an exception. Controllers raise
  `result.as_app_exception()`.
- **Every message has a policy** at registration (`PUBLIC_POINT`,
  `DEVICE_POINT`). There is no user auth by design (TZ §17).
- **Handlers are factories**; the mediator builds one per message.
- **Ports are Protocols**, asserted with `ensure_isimplementation`.
- Markers: `TOFIX` bug · `HOTBUG` important bug not fixable now ·
  `HARDCODED` value that should be config · `TODO` anything else.

## Things that will bite you

- **All logic runs on frame time (`ts`), not the server clock** (TZ §4). The
  only wall-clock use is the link age on the Device page.
- **`on_minute` must stay pure.** It is the same code ML runs to make training
  windows; a DB call or a clock read in there splits training from production.
- The pipeline is synchronous and never awaits Postgres: rows go through
  `PersistenceQueue` (write-behind, retries every second).
- Alert ids are allocated in memory (`MonitoringEngine`), the writer upserts by
  id. Do not insert alerts anywhere else.
- History frames (flag bit 7) are persisted but never sent to `/live` and
  never narrated by the LLM.
- `null` means "no data" everywhere. Never fill it with 0 or the last value.
- User-facing text is English (Space Apps rule), unlike the CRM.

## Running

```
docker run -d --name vigil-pg -e POSTGRES_USER=vigil -e POSTGRES_PASSWORD=vigil \
  -e POSTGRES_DB=vigil -p 5432:5432 postgres:17-alpine
venv/bin/python serve.py                          # dev, auto-reload; prod: -m src.main
venv/bin/python -m scripts.smoke_feed --days 14 --live-min 20 --hypoxia
venv/bin/python -m pytest -q && venv/bin/ruff check src tests scripts
```
