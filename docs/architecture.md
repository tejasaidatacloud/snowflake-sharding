# Architecture: Snowflake Sharding — Deep Dive

## Why Sharding?

A single database table hits physical limits:
- Disk I/O becomes a bottleneck beyond ~10M rows on a single machine
- Writes contend on the same table locks
- Backups / vacuuming pause the whole dataset

**Horizontal sharding** solves this by splitting data across N databases (shards),
each holding 1/N of the rows. A router decides which shard owns each record.

---

## The Snowflake ID (64 bits)

Inspired by Twitter's Snowflake and Discord's Snowflake, our IDs encode three things:

```
Bit 63                                                         Bit 0
 |   41 bits (timestamp)    |  10 bits (shard)  |  12 bits (seq)  |
```

| Field      | Bits | Max value    | Purpose |
|------------|------|-------------|---------|
| timestamp  | 41   | ~2.2 trillion| ms since epoch → IDs are **time-sortable** |
| shard_id   | 10   | 1023         | Which shard owns this record |
| sequence   | 12   | 4095         | Burst capacity: 4096 IDs/ms/shard |

### Why embed the shard in the ID?

Without it, routing an existing ID requires a **lookup table** (id → shard).
That lookup table itself becomes a bottleneck and single point of failure.

With the shard embedded: routing is a **bitwise shift + mask — O(1), no I/O**.

---

## The Router

```python
# Route an existing ID to its shard (reading):
shard_index = (user_id >> 12) & 0x3FF   # extract bits [21..12]
shard_index = shard_index % NUM_SHARDS  # normalize if NUM_SHARDS changed

# Assign a shard for a new user (writing):
shard_index = hash(email) % NUM_SHARDS  # deterministic by email
```

The email-hash assignment means the same email always maps to the same shard,
which makes duplicate detection within a shard reliable.

---

## Request Flow

### Create user (POST /users/)
```
Client → FastAPI → hash(email) % 8 → shard_index
                 → SnowflakeGenerator(shard_index).next_id()
                 → INSERT INTO shard_{shard_index}.db
                 → return UserResponse (includes shard_id + id_breakdown)
```

### Read user (GET /users/{id})
```
Client → FastAPI → (id >> 12) & 0x3FF % 8 → shard_index
                 → SELECT * FROM shard_{shard_index}.db WHERE id = ?
                 → return UserResponse
```

### List all users (GET /users/)
```
Client → FastAPI → for each shard: SELECT * FROM shard_N.db
                 → merge + sort by id (time order)
                 → return paginated list
```
This is the only "scatter-gather" operation — it touches all 8 shards.
In production, a search index (Elasticsearch, Typesense) handles cross-shard queries.

---

## Expanding Shards: 8 → 16

When you need to scale beyond 8 shards:

1. **Update the constant**: `NUM_SHARDS = 16` in `shard_router.py`
2. **Initialize new shards**: `ShardManager` creates `shard_8.db` … `shard_15.db`
3. **Migrate existing data**: Run a migration script that:
   - Reads every row from `shard_0..7`
   - Recalculates `shard_id = original_shard_id % 16`
   - Moves rows to the new correct shard if they differ
4. **Zero-downtime strategy**: Use consistent hashing so only 1/2 of the data moves (not all of it)

The `% NUM_SHARDS` modulo in `ShardRouter.route()` is intentional:
it makes existing IDs (which have their old shard embedded) still route correctly
to valid shards during and after migration.

---

## What This Project Demonstrates

| Concept | Implementation |
|---------|---------------|
| Horizontal sharding | 8 SQLite databases acting as independent servers |
| Snowflake ID | `app/core/snowflake.py` — 64-bit time+shard+seq |
| O(1) routing | `ShardRouter.route()` — pure bitwise ops |
| Deterministic write routing | email hash % NUM_SHARDS |
| Scatter-gather query | `list_users()` — merges across all shards |
| Soft delete | `is_active` flag, not physical row removal |
| Expandable design | `NUM_SHARDS` is the single scaling lever |
| Monitoring | `/shards/stats` reports per-shard row counts |

---

## Production Differences

In a real system each "shard" would be:
- A separate PostgreSQL or MySQL instance (often on its own VM/container)
- Connected via a connection pool (PgBouncer, SQLAlchemy)
- Replicated (primary + 1–2 read replicas per shard)
- Monitored via Prometheus / Grafana

The routing logic is identical — the shard ID in the Snowflake ID points
to a **connection pool name**, not a file path. Everything else is the same.
