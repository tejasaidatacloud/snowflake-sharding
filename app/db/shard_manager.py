"""
shard_manager.py — Creates and manages one SQLite database per shard
---------------------------------------------------------------------
Each shard is a separate .db file on disk, simulating an independent
database server. In production this would be a separate PostgreSQL or
MySQL instance; SQLite lets us demonstrate the concept locally.

The ShardManager is a singleton — initialized once at startup,
then reused for every request via FastAPI's dependency injection.
"""

import sqlite3
import os
from pathlib import Path
from app.core.shard_router import NUM_SHARDS

# All shard files live in a dedicated directory at project root
SHARD_DIR = Path(__file__).resolve().parents[3] / "shards"

# SQL for the users table — identical schema on every shard
CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY,   -- Snowflake ID (encodes shard + time)
    username    TEXT    NOT NULL UNIQUE,
    email       TEXT    NOT NULL UNIQUE,
    full_name   TEXT,
    region      TEXT,                  -- e.g. "us-east", "eu-west"
    created_at  TEXT    NOT NULL,      -- ISO-8601 timestamp
    is_active   INTEGER NOT NULL DEFAULT 1
);
"""

# Optional index — speeds up email lookups within a shard
CREATE_EMAIL_INDEX = """
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
"""


class ShardManager:
    """
    Owns the connection pool to all shard databases.

    Usage:
        manager = ShardManager()          # call once at app startup
        conn = manager.get_connection(3)  # get connection to shard 3
    """

    def __init__(self):
        SHARD_DIR.mkdir(parents=True, exist_ok=True)
        self._connections: dict[int, sqlite3.Connection] = {}
        self._initialize_all_shards()

    def _initialize_all_shards(self):
        """Open (or create) each shard database and apply the schema."""
        for shard_id in range(NUM_SHARDS):
            db_path = SHARD_DIR / f"shard_{shard_id}.db"
            conn = sqlite3.connect(str(db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row   # rows accessible like dicts
            conn.execute("PRAGMA journal_mode=WAL;")  # better concurrency
            conn.execute(CREATE_USERS_TABLE)
            conn.execute(CREATE_EMAIL_INDEX)
            conn.commit()
            self._connections[shard_id] = conn

    def get_connection(self, shard_id: int) -> sqlite3.Connection:
        """Return the live connection for the given shard."""
        if shard_id not in self._connections:
            raise ValueError(f"Shard {shard_id} does not exist (NUM_SHARDS={NUM_SHARDS})")
        return self._connections[shard_id]

    def get_shard_stats(self) -> list[dict]:
        """Return row counts for every shard — useful for monitoring."""
        stats = []
        for shard_id, conn in self._connections.items():
            cursor = conn.execute("SELECT COUNT(*) FROM users")
            count  = cursor.fetchone()[0]
            db_path = SHARD_DIR / f"shard_{shard_id}.db"
            size_kb = round(os.path.getsize(db_path) / 1024, 2)
            stats.append({
                "shard_id":   shard_id,
                "user_count": count,
                "db_size_kb": size_kb,
                "db_file":    str(db_path),
            })
        return stats

    def close_all(self):
        """Close all connections — called on app shutdown."""
        for conn in self._connections.values():
            conn.close()
        self._connections.clear()


# Module-level singleton — imported by routers via dependency injection
_manager_instance: ShardManager | None = None


def get_shard_manager() -> ShardManager:
    """
    FastAPI dependency: returns the shared ShardManager instance.

    Example usage in a router:
        @router.get("/users/{user_id}")
        def get_user(user_id: int, manager: ShardManager = Depends(get_shard_manager)):
            ...
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ShardManager()
    return _manager_instance
