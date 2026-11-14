# Vigil — server

Health monitoring backend for astronauts (NASA Space Apps 2026, challenge
*Create Health Monitoring Software for Astronauts on Space Missions*).

The server receives 1 Hz frames from crew wearables (or the virtual device),
folds them into minutes, works out the context (sleep / rest / exercise),
learns each person's own normal ranges, raises Watch / Alert / Critical
levels, names the deviation pattern, writes a short explanation and builds a
daily report for the flight surgeon. It is one process with in-memory state
and Postgres for minutes and events.

The specification is [BACKEND_TZ.md](BACKEND_TZ.md); the plan is [PLAN.md](PLAN.md).

## Quick start

```bash
cp .env.example .env                 # optional: defaults work as is
docker compose up --build            # postgres + backend on :8000
# with the LLM: OLLAMA_URL=http://ollama:11434 docker compose --profile llm up
open http://localhost:8000/docs      # OpenAPI
```

Without Docker:

```bash
python -m venv venv && venv/bin/pip install -r requirements.txt
cp .env.example .env                 # POSTGRES_* point at a Postgres
venv/bin/python serve.py            # dev: auto-reload, http://localhost:8000/docs
# production: venv/bin/python -m src.main
```

Feed it without the real simulator (14 days of history, then 20 live minutes
with a falling SpO2):

```bash
venv/bin/python -m scripts.smoke_feed --url ws://localhost:8000/ingest --days 14 --live-min 20 --hypoxia
```

## API

| Method | Path | Screen |
|---|---|---|
| WS | `/ingest` | binary 32-byte frames (`src/vigil_types/ingest/frame.py`) |
| WS | `/live?crew=1` | `tick`, `alert`, `level`, `baseline` messages |
| GET | `/crew` | Crew |
| GET | `/crew/{id}/today` | Today |
| GET | `/crew/{id}/metric/{m}?range=1h\|24h\|7d` | metric chart |
| GET | `/crew/{id}/alerts?open=1` | Notices |
| POST | `/alerts/{id}/ack` | Notices, Critical |
| GET, POST | `/crew/{id}/checkin` | Check-in |
| GET | `/crew/{id}/sleep` | Sleep |
| GET | `/crew/{id}/device` | Device |
| GET, PUT | `/crew/{id}/report/{day}` | Report |
| POST | `/crew/{id}/report/{day}/queue` | Report |
| GET | `/radiation` | Radiation (NASA OSDR RadLab) |
| GET, POST | `/sim/state`, `/sim/scenario`, `/sim/speed`, `/sim/reset` | demo panel, proxied to vdev |
| GET | `/health` | — |

## Inputs from the rest of the team

| File | From | Missing → |
|---|---|---|
| `ml/models/pattern.json`, `pattern_meta.json` | ML | patterns by rule (TZ §8.3) |
| Ollama model `vigil-narrator` (`OLLAMA_URL`) | ML | template texts |
| `docs/actions.yaml` | D2 | one generic action |
| `data/radlab/*.json` | EMB | empty Radiation page |

RadLab files are what the OSDR API returns, e.g.
`https://visualization.osdr.nasa.gov/radlab/api/?spacecraft=ISS&timestamp%3E=2022-04-01&timestamp%3C2022-04-15&absorbed_dose_rate&format=json`.
The unit of `absorbed_dose_rate` is not stated next to the data; set
`RADLAB_RATE_UNIT` once it is confirmed.

## Data and licences

NASA OSDR RadLab (open NASA data) for radiation. Physiological streams come
from the virtual device built on PPG-DaLiA (CC BY 4.0), BIDMC (ODC-By 1.0) and
Sleep-accel (ODC-By 1.0); see PLAN.md §5. No real astronaut vitals are used.

## Architecture

Layered like the Anbor CRM v2: contracts (`src/vigil_types`) → API →
application (CQRS handlers through a mediator) → domain (pure pipeline) →
data access (SQLAlchemy) → infra (DI containers, event subscribers). See
[CLAUDE.md](CLAUDE.md).

## Licence

Apache-2.0, see [LICENSE](LICENSE).
