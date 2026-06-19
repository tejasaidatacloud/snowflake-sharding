<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi" />
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python" />
  <img src="https://img.shields.io/badge/SQLite-per--shard-003B57?style=flat-square&logo=sqlite" />
  <img src="https://img.shields.io/badge/Snowflake_IDs-64--bit-00C7FF?style=flat-square" />
  <img src="https://img.shields.io/badge/Shards-8-blueviolet?style=flat-square" />
</p>

<h1 align="center">❄️ Snowflake Sharding — Live Visualizer</h1>

<p align="center">
  A fully working demonstration of <strong>database sharding</strong> using <strong>Snowflake IDs</strong> —
  built with FastAPI, SQLite, and a real-time browser dashboard.
  Every user you create is routed to the correct shard in O(1) with zero lookup tables.
</p>

---

## What Is This?

This project implements two foundational distributed-systems concepts end-to-end:

1. **Snowflake IDs** — 64-bit integers that encode *when* a record was created and *where* it lives, all in a single number.
2. **Database Sharding** — splitting one logical database across multiple physical databases (shards) to distribute load and scale horizontally.

The live dashboard lets you watch routing happen in real time: create a user, see which shard they land on, and inspect the exact bit breakdown of their Snowflake ID.

---

## Architecture

### The 64-bit Snowflake ID

```
 63        22 21       12 11        0
 ┌──────────┬──────────┬────────────┐
 │timestamp │ shard_id │  sequence  │
 │ 41 bits  │ 10 bits  │  12 bits   │
 └──────────┴──────────┴────────────┘
```

| Field | Bits | Range | Purpose |
|-------|------|-------|---------|
| Timestamp | 41 | ~69 years | Milliseconds since custom epoch (2024-01-01). Makes IDs time-sortable. |
| Shard ID | 10 | 0–1023 | Which physical database holds this record. |
| Sequence | 12 | 0–4095 | Burst counter within the same millisecond per shard. |

**Result:** up to **4,096 unique IDs per shard per millisecond**, globally sortable, with the destination shard embedded — no lookup table ever needed.

### Shard Routing (O(1))

```
User creation:
  email → hash() → % NUM_SHARDS → shard_index
                                        │
                          SnowflakeGenerator(shard_index).next_id()
                                        │
                          INSERT INTO shard_{index}.db

User lookup:
  snowflake_id → extract bits [21..12] → % NUM_SHARDS → shard_index
                                                              │
                                           SELECT FROM shard_{index}.db
```

The shard index is never stored in a routing table. It is **derived arithmetically** from the ID itself. Lookup is always a single database hit.

### System Diagram

```
                         ┌─────────────────────┐
                         │    FastAPI Backend   │
                         │                     │
  POST /users/  ────────►│  ShardRouter        │
                         │  .assign_shard()    │──► shard_0.db
                         │                     │
  GET /users/{id} ──────►│  ShardRouter        │──► shard_1.db
                         │  .route(id)         │
                         │                     │──► shard_2.db
  GET /shards/stats ────►│  ShardManager       │
                         │  .get_shard_stats() │──► ...
                         │                     │
                         │  SnowflakeGenerator │──► shard_7.db
                         │  (one per shard)    │
                         └─────────────────────┘
                                   │
                         ┌─────────▼─────────┐
                         │  Browser Dashboard │
                         │  • Shard cards     │
                         │  • Bar chart       │
                         │  • Activity feed   │
                         │  • ID breakdown    │
                         └───────────────────┘
```

### File Structure

```
snowflake-sharding/
├── app/
│   ├── main.py                  # FastAPI app, CORS, lifespan, static mount
│   ├── core/
│   │   ├── snowflake.py         # 64-bit ID generator (thread-safe)
│   │   └── shard_router.py      # Routes IDs → shards, O(1) bit extraction
│   ├── db/
│   │   └── shard_manager.py     # SQLite connections, one per shard
│   ├── models/
│   │   └── user.py              # Pydantic schemas (ID serialized as string)
│   ├── routers/
│   │   └── users.py             # CRUD endpoints
│   └── static/
│       └── index.html           # Single-file dashboard (vanilla JS + Chart.js)
├── shards/                      # Auto-generated .db files (git-ignored)
├── tests/
│   └── test_sharding.py
├── docs/
│   └── architecture.md
├── render.yaml                  # One-click Render deployment
├── requirements.txt
└── README.md
```

---

## Key Design Decisions

### Why Snowflake IDs instead of UUIDs?
- **Sortable by time** — Snowflake IDs are monotonically increasing. `ORDER BY id` = chronological order. UUIDs are random.
- **Shard embedded** — the destination shard is baked in. No routing table, no extra DB call.
- **Smaller** — 64-bit integer vs 128-bit UUID. Faster indexes, less storage.

### Why hash(email) for shard assignment?
- **Deterministic** — the same email always routes to the same shard. Re-creating a deleted user won't scatter records.
- **Even distribution** — Python's `hash()` spreads well across `% NUM_SHARDS`.

### Why is `id` returned as a string in the API?
JavaScript's `Number.MAX_SAFE_INTEGER` is 2⁵³ − 1 = `9,007,199,254,740,991`. Snowflake IDs are 64-bit and exceed this. `JSON.parse()` would silently round them, corrupting lookups. The API returns `id` as a string; the frontend never converts it to a JS number.

### Why SQLite per shard (instead of one PostgreSQL)?
For local development and demos, one SQLite file per shard perfectly simulates independent database servers with zero infrastructure. The `ShardManager` and connection interface would be identical with PostgreSQL — swap the driver, not the architecture.

---

## Running Locally

```bash
git clone https://github.com/tejasaidatacloud/snowflake-sharding.git
cd snowflake-sharding

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt

uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000** — the dashboard loads automatically.

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/users/` | Create a user, auto-routes to a shard |
| `GET` | `/users/{id}` | Fetch by Snowflake ID (O(1) shard lookup) |
| `GET` | `/users/` | List all users (scatter-gather across all shards) |
| `DELETE` | `/users/{id}` | Soft-delete (sets `is_active = 0`) |
| `GET` | `/shards/stats` | Row counts + DB size for every shard |
| `GET` | `/health` | Health check |

Full interactive docs: **http://127.0.0.1:8000/docs**

---

## Deploying to Render (Free)

1. Push this repo to GitHub.
2. Go to [render.com](https://render.com) → **New → Web Service**.
3. Connect your GitHub repo.
4. Render detects `render.yaml` automatically — click **Deploy**.
5. Your live URL will be `https://snowflake-sharding.onrender.com` (or similar).

> **Note:** Render's free tier uses an ephemeral filesystem — shard `.db` files reset on each deploy. Use the **Generate** button to repopulate data after deployment. For persistent data, mount a Render Disk or swap SQLite for PostgreSQL.

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Scaling Beyond 8 Shards

To double from 8 → 16 shards:

1. Update `NUM_SHARDS = 16` in `app/core/shard_router.py`.
2. The `ShardRouter.route()` uses `% NUM_SHARDS`, so existing IDs re-route correctly.
3. Migrate data from old shards to new ones (see `docs/architecture.md`).

The Snowflake ID format supports up to **1,024 shards** before the bit layout needs changing.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI 0.115 |
| Server | Uvicorn (ASGI) |
| Validation | Pydantic v2 |
| Storage | SQLite (one `.db` per shard) |
| ID generation | Custom Snowflake (thread-safe) |
| Frontend | Vanilla JS + Chart.js |
| Deployment | Render |

---

## License

MIT
