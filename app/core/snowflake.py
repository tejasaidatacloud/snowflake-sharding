"""
snowflake.py — Snowflake-inspired 64-bit ID Generator
------------------------------------------------------
Produces unique, time-sortable IDs that embed the target shard
so the router can determine WHERE data lives without a lookup table.

64-bit layout:
  [63..22] timestamp  — 41 bits — ms since EPOCH (good until ~2090)
  [21..12] shard_id   — 10 bits — supports up to 1024 shards
  [11..0]  sequence   — 12 bits — 4096 IDs per shard per millisecond
"""

import time
import threading

# Custom epoch: 2024-01-01 00:00:00 UTC in milliseconds.
# Using a recent epoch keeps the timestamp bits small and extends ID space.
EPOCH_MS = 1_704_067_200_000

# Bit layout constants
SHARD_BITS     = 10   # bits reserved for shard identifier
SEQUENCE_BITS  = 12   # bits reserved for sequence within the same ms

MAX_SHARD_ID   = (1 << SHARD_BITS)   - 1   # 1023
MAX_SEQUENCE   = (1 << SEQUENCE_BITS) - 1   # 4095

SHARD_SHIFT     = SEQUENCE_BITS              # 12
TIMESTAMP_SHIFT = SHARD_BITS + SEQUENCE_BITS # 22


class SnowflakeGenerator:
    """
    Thread-safe Snowflake ID generator bound to a specific shard.

    Each shard should own one instance of this generator.
    Calling .next_id() returns the next unique 64-bit integer for that shard.
    """

    def __init__(self, shard_id: int):
        if not (0 <= shard_id <= MAX_SHARD_ID):
            raise ValueError(f"shard_id must be 0–{MAX_SHARD_ID}, got {shard_id}")

        self.shard_id    = shard_id
        self._sequence   = 0
        self._last_ms    = -1
        self._lock       = threading.Lock()

    def next_id(self) -> int:
        """Generate the next unique Snowflake ID for this shard."""
        with self._lock:
            now_ms = self._current_ms()

            if now_ms == self._last_ms:
                # Same millisecond — increment sequence
                self._sequence = (self._sequence + 1) & MAX_SEQUENCE
                if self._sequence == 0:
                    # Sequence exhausted; busy-wait for next ms
                    now_ms = self._wait_next_ms(self._last_ms)
            else:
                # New millisecond — reset sequence
                self._sequence = 0

            self._last_ms = now_ms

            return (
                ((now_ms - EPOCH_MS) << TIMESTAMP_SHIFT) |
                (self.shard_id       << SHARD_SHIFT)     |
                self._sequence
            )

    # ------------------------------------------------------------------
    # Static helpers — decompose any Snowflake ID back into its parts
    # ------------------------------------------------------------------

    @staticmethod
    def extract_shard_id(snowflake_id: int) -> int:
        """Pull the shard_id out of a Snowflake ID (no DB lookup needed)."""
        return (snowflake_id >> SHARD_SHIFT) & MAX_SHARD_ID

    @staticmethod
    def extract_timestamp_ms(snowflake_id: int) -> int:
        """Return the creation timestamp in milliseconds since Unix epoch."""
        return (snowflake_id >> TIMESTAMP_SHIFT) + EPOCH_MS

    @staticmethod
    def decompose(snowflake_id: int) -> dict:
        """Return all three components of a Snowflake ID as a dict."""
        timestamp_ms = (snowflake_id >> TIMESTAMP_SHIFT) + EPOCH_MS
        shard_id     = (snowflake_id >> SHARD_SHIFT) & MAX_SHARD_ID
        sequence     = snowflake_id & MAX_SEQUENCE
        return {
            "snowflake_id":   snowflake_id,
            "timestamp_ms":   timestamp_ms,
            "shard_id":       shard_id,
            "sequence":       sequence,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _current_ms() -> int:
        return int(time.time() * 1000)

    def _wait_next_ms(self, last_ms: int) -> int:
        now = self._current_ms()
        while now <= last_ms:
            now = self._current_ms()
        return now
