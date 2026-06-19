# LinkedIn Post Draft

---

🧵 I built a live database sharding visualizer — and you can watch every user get routed to its shard in real time.

Here's how it works 👇

**The core idea: Snowflake IDs**

Every user gets a 64-bit integer that encodes three things in one number:

```
[ 41-bit timestamp | 10-bit shard_id | 12-bit sequence ]
```

That means when you look up a user, you never ask "which shard is this in?" — you just extract bits 21–12 from the ID. O(1). No routing table. No extra database call. Ever.

**The architecture in one diagram:**

```
email → hash() → % 8 shards → SnowflakeGenerator → INSERT into shard_N.db
                                      ↕
snowflake_id → extract bits → shard index → SELECT from shard_N.db
```

8 independent SQLite databases. One FastAPI backend. One line to scale to 16 shards.

**Why not UUIDs?**
→ UUIDs are random. Snowflake IDs are time-sortable.
→ UUIDs carry no routing info. Snowflake IDs embed the shard.
→ 64-bit int vs 128-bit UUID. Smaller indexes, faster queries.

**One gotcha I had to solve:**
JavaScript's `Number.MAX_SAFE_INTEGER` is 2⁵³ − 1. Snowflake IDs exceed it. `JSON.parse()` silently rounds them — and your lookups break. Fix: return `id` as a string from the API. Never let JS convert it to a number.

**What the dashboard shows:**
✅ 8 shard cards updating live as users are created
✅ Distribution bar chart across all shards
✅ Per-user routing trace (Source → Router → Shard)
✅ Full 64-bit ID breakdown — timestamp, shard bits, sequence counter
✅ Bulk fake profile generator to stress-test distribution

🔗 Live demo: [YOUR_RENDER_URL]
⭐ GitHub: https://github.com/YOUR_USERNAME/snowflake-sharding

Built with: FastAPI · SQLite · Vanilla JS · Chart.js · Render

What distributed systems pattern would you want to see visualized next? Drop it below 👇

#distributedsystems #databases #backend #systemdesign #fastapi #python #opensource
