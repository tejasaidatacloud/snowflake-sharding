"""
test_sharding.py — Unit and integration tests
Run with:  pytest tests/ -v
"""

import time
import pytest
from fastapi.testclient import TestClient

from app.main              import app
from app.core.snowflake    import SnowflakeGenerator
from app.core.shard_router import ShardRouter, NUM_SHARDS

client = TestClient(app)

# Unique suffix per test run so repeated runs don't collide on unique constraints
_RUN = str(int(time.time() * 1000))[-6:]


class TestSnowflakeID:

    def test_ids_are_unique(self):
        gen = SnowflakeGenerator(shard_id=0)
        ids = {gen.next_id() for _ in range(1000)}
        assert len(ids) == 1000

    def test_ids_are_monotonically_increasing(self):
        gen = SnowflakeGenerator(shard_id=0)
        ids = [gen.next_id() for _ in range(100)]
        assert ids == sorted(ids)

    def test_shard_id_embedded_correctly(self):
        for shard_id in range(NUM_SHARDS):
            gen = SnowflakeGenerator(shard_id=shard_id)
            uid = gen.next_id()
            assert SnowflakeGenerator.extract_shard_id(uid) == shard_id

    def test_decompose_roundtrip(self):
        gen  = SnowflakeGenerator(shard_id=3)
        uid  = gen.next_id()
        info = SnowflakeGenerator.decompose(uid)
        assert info["shard_id"] == 3
        assert info["snowflake_id"] == uid
        assert info["timestamp_ms"] > 0
        assert 0 <= info["sequence"] <= 4095


class TestShardRouter:

    def test_route_is_deterministic(self):
        gen = SnowflakeGenerator(shard_id=5)
        uid = gen.next_id()
        assert ShardRouter.route(uid) == ShardRouter.route(uid)

    def test_route_within_bounds(self):
        for shard_id in range(NUM_SHARDS):
            gen = SnowflakeGenerator(shard_id=shard_id)
            uid = gen.next_id()
            assert 0 <= ShardRouter.route(uid) < NUM_SHARDS

    def test_assign_shard_hint_is_deterministic(self):
        hint = hash("user@example.com")
        assert ShardRouter.assign_shard(hint=hint) == ShardRouter.assign_shard(hint=hint)


class TestUsersAPI:

    def _make_user(self, suffix: str = "") -> dict:
        payload = {
            "username":  f"tu{_RUN}{suffix}",
            "email":     f"tu{_RUN}{suffix}@example.com",
            "full_name": "Test User",
            "region":    "us-east",
        }
        resp = client.post("/users/", json=payload)
        assert resp.status_code == 201, resp.text
        return resp.json()

    def test_create_user_returns_201(self):
        data = self._make_user("a")
        assert "id" in data
        assert isinstance(data["id"], str), "ID must be a string to preserve 64-bit precision"
        assert 0 <= data["shard_id"] < NUM_SHARDS

    def test_get_user_by_id(self):
        created = self._make_user("b")
        resp = client.get(f"/users/{created['id']}")
        assert resp.status_code == 200
        assert str(resp.json()["id"]) == str(created["id"])

    def test_get_nonexistent_user_returns_404(self):
        assert client.get("/users/999999999999").status_code == 404

    def test_list_users_includes_created(self):
        created = self._make_user("c")
        ids = [u["id"] for u in client.get("/users/?limit=1000").json()]
        assert created["id"] in ids

    def test_list_users_are_sorted_by_id(self):
        ids = [u["id"] for u in client.get("/users/?limit=1000").json()]
        assert ids == sorted(ids)

    def test_delete_user_returns_204(self):
        created = self._make_user("d")
        assert client.delete(f"/users/{created['id']}").status_code == 204

    def test_deleted_user_absent_from_list(self):
        created = self._make_user("e")
        client.delete(f"/users/{created['id']}")
        ids = [u["id"] for u in client.get("/users/?limit=1000").json()]
        assert created["id"] not in ids

    def test_duplicate_email_returns_409(self):
        created = self._make_user("f")
        resp = client.post("/users/", json={
            "username": f"other{_RUN}",
            "email":    created["email"],
        })
        assert resp.status_code == 409

    def test_shard_stats_endpoint(self):
        resp = client.get("/shards/stats")
        assert resp.status_code == 200
        assert len(resp.json()) == NUM_SHARDS


class TestShardDistribution:

    def test_users_spread_across_multiple_shards(self):
        shards_used = set()
        for i in range(16):
            resp = client.post("/users/", json={
                "username": f"du{_RUN}{i}",
                "email":    f"du{_RUN}{i}@domain{i}.com",
            })
            if resp.status_code == 201:
                shards_used.add(resp.json()["shard_id"])
        assert len(shards_used) > 1, f"All users landed on one shard: {shards_used}"
