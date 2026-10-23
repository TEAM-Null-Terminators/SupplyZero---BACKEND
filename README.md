# SupplyZero backend

Async FastAPI backend for cold-chain telemetry, deterministic shelf-life estimates, decision records, MQTT ingestion, and real-time updates. It follows the supplied SupplyZero PRD while keeping kinetic and financial calculations in deterministic Python rules; no LLM is used for state or action selection.

## Run locally

Requires Python 3.11+. The default SQLite database is for development; PostgreSQL/TimescaleDB is configured in Compose.

```powershell
cd SupplyZero
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
python -m app.seed
uvicorn app.main:app --reload
```

Interactive API docs: http://localhost:8000/docs. For the full local stack, use `docker compose up --build`; the compose broker is intentionally anonymous and suitable only for local demos. Set broker credentials and TLS for deployment.

### Start backend and dashboard together (Windows)

From PowerShell in the project folder, run this single command:

```powershell
powershell -ExecutionPolicy Bypass -File .\run-supplyzero.ps1
```

The launcher creates a local virtual environment and installs missing dependencies on its first run, then opens separate backend and frontend windows. Keep both open. Visit http://127.0.0.1:5173 for the dashboard and http://127.0.0.1:8000/docs for the API. Close both windows to stop the services.

## Run the dashboard

Start the API as above, then open a second PowerShell window:

```powershell
cd "C:\Users\SUYASH SRIVASTAVA\OneDrive\Documents\SupplyZero\frontend"
npm install
npm run dev
```

Open http://127.0.0.1:5173. The frontend includes a local demo fallback if the API or WebSocket is unavailable.

## Demo workflow

Create a shipment using a seeded product UUID from `GET /api/products`, then run:

```powershell
python -m app.simulator --shipment SZ-DEMO-001 --scenario compressor_failure
```

Available scenarios: `normal`, `compressor_failure`, `door_open`, `heatwave`, `freeze`, and `sensor_dropout`. Scenario injection is also available at `POST /api/sim/scenario`.

## Engineering notes

- Telemetry uses a unique `(shipment_id, ts)` constraint and sorted-history replay, so duplicate messages are no-ops and late readings are replayed deterministically. A process-local shipment lock reduces races in a single worker. For multi-worker PostgreSQL deployments, use a per-shipment advisory lock or partition messages by shipment before scaling ingestion.
- State snapshots, excursions, recommendations, and audit records are append-oriented. Recommendation workflow status is updated in place, with each transition copied to the append-only audit log.
- Missing telemetry intervals receive a conservative configurable degradation uplift. MKT assumes a configurable chemistry activation energy default; tune using validated product data before operational use.
- Routing calls have a <=1.49 s timeout, a 15 s circuit breaker, Redis cache when available, and a Haversine fallback. Fallback distance is approximate and marked in scoring details.
- Pharma hard-stop recommendations are quarantine only. Approval records QA disposition; this service does not release pharma goods. All example profiles are illustrative and not validated quality limits.
- `AUTO_EXECUTE` is off by default. Enabling it records AUTO_EXECUTED for eligible non-pharma recommendations; carrier booking is outside this backend.
- REST: `/api/shipments`, detail, telemetry, forecast; `/api/products`, `/api/hubs`; recommendation list/approve/reject; quarantine; demo scenario; impact summary; audit; `/health`. WebSocket: `/ws/stream`.

## TimescaleDB

The compose database image includes TimescaleDB. `Telemetry` has a stable unique key for idempotency. A production migration should create a hypertable with `shipment_id` and `ts` in its composite unique key; current startup uses SQLAlchemy schema creation for portability and does not auto-convert tables. Add reviewed Alembic migrations before production schema evolution.

## Tests

```powershell
pytest
```

Tests pin Arrhenius, Q10, MKT, constant-temperature consumption, ordering, gap handling, and hard-stop behavior to analytical constants. Product parameters must be replaced with QA-validated stability data for real goods.
