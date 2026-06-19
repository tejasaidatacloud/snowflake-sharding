"""
shard_router.py — Routes Snowflake IDs to the correct shard
------------------------------------------------------------
The router's job is simple: given a Snowflake ID, tell the system
WHICH shard database holds (or should hold) the data.

Because the shard_id is embedded inside every Snowflake ID, this is
a pure bit-extraction operation — O(1), no database lookups, no network calls.

Design note on expandability
-----------------------------
We store NUM_SHARDS in one place. When you double the shards (8 → 16),
you update NUM_SHARDS, run the migration script (see docs/architecture.md),
and everything re-routes correctly. No other code changes.
"""

from app.core.snowflake import SnowflakeGenerator, MAX_SHARD_ID

# ── Configuration ────────────────────────────────────────────────────────────
# Change this one constant to scale up.  Must be a power of 2.
NUM_SHARDS = 8
# ─────────────────────────────────────────────────────────────────────────────

# One generator per shard, created at module load time.
# Each generator is bound to its shard_id so the embedded bits are correct.
_generators: dict[int, SnowflakeGenerator] = {
    shard_id: SnowflakeGenerator(shard_id)
    for shard_id in range(NUM_SHARDS)
}


class ShardRouter:
    """
    Stateless helper that answers two questions:
      1. Which shard should store a NEW user?  → assign_shard()
      2. Which shard stores an EXISTING user?  → route()
    """

    @staticmethod
    def assign_shard(hint: int | None = None) -> int:
        """
        Pick a shard for a new user.

        Args:
            hint: optional integer (e.g. hash of email) to make the assignment
                  deterministic for the same input.  Pass None for round-robin
                  style (uses the current timestamp % NUM_SHARDS).

        Returns:
            shard index in [0, NUM_SHARDS)
        """
        if hint is not None:
            return hint % NUM_SHARDS
        # Default: distribute evenly by time — simple and effective
        import time
        return int(time.time() * 1000) % NUM_SHARDS

    @staticmethod
    def route(snowflake_id: int) -> int:
        """
        Extract the shard index from an existing Snowflake ID.

        The raw shard_id embedded in the ID may have been generated when
        NUM_SHARDS was different. We apply modulo so the value always
        falls within the current shard range.

        Returns:
            shard index in [0, NUM_SHARDS)
        """
        raw_shard = SnowflakeGenerator.extract_shard_id(snowflake_id)
        return raw_shard % NUM_SHARDS

    @staticmethod
    def generate_id(shard_index: int) -> int:
        """
        Generate a new Snowflake ID for the given shard.

        Args:
            shard_index: which shard will store this record

        Returns:
            64-bit Snowflake ID with shard_index embedded
        """
        return _generators[shard_index].next_id()

    @staticmethod
    def all_shards() -> list[int]:
        """Return all active shard indices."""
        return list(range(NUM_SHARDS))

    @staticmethod
    def decompose(snowflake_id: int) -> dict:
        """Expose full decomposition for debugging / API responses."""
        return SnowflakeGenerator.decompose(snowflake_id)
