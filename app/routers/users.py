"""
users.py — REST endpoints for user management
----------------------------------------------
Every endpoint uses the ShardRouter to find the right shard,
then runs a simple SQL query against only that shard's connection.

Key insight: we never query all 8 shards for a single user lookup —
the shard is embedded in the ID, so we go straight to the right DB.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.shard_router import ShardRouter
from app.db.shard_manager  import ShardManager, get_shard_manager
from app.models.user        import UserCreate, UserResponse, ShardStats

router = APIRouter()


# ── POST /users/ ──────────────────────────────────────────────────────────────

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    manager: ShardManager = Depends(get_shard_manager),
):
    """
    Create a new user.

    Steps:
      1. Pick a shard (hinted by the email hash for determinism).
      2. Generate a Snowflake ID embedding that shard's index.
      3. Insert into the correct shard database.
      4. Return the full user with shard metadata.
    """
    # Step 1 — deterministic shard assignment using email hash
    shard_index = ShardRouter.assign_shard(hint=hash(payload.email))

    # Step 2 — generate a Snowflake ID for this shard
    user_id = ShardRouter.generate_id(shard_index)

    # Step 3 — insert into the correct shard
    created_at = datetime.now(timezone.utc).isoformat()
    conn = manager.get_connection(shard_index)

    # Pre-check: email uniqueness within this shard (same email always routes here)
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (payload.email,)).fetchone()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists.",
        )

    try:
        conn.execute(
            """
            INSERT INTO users (id, username, email, full_name, region, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (user_id, payload.username, payload.email,
             payload.full_name, payload.region, created_at),
        )
        conn.commit()
    except Exception as exc:
        if "UNIQUE constraint" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username or email already exists.",
            )
        raise HTTPException(status_code=500, detail=str(exc))

    # Step 4 — build and return the response
    return UserResponse(
        id=user_id,
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        region=payload.region,
        created_at=created_at,
        is_active=True,
        shard_id=shard_index,
        id_breakdown=ShardRouter.decompose(user_id),
    )


# ── GET /users/{user_id} ──────────────────────────────────────────────────────

@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    manager: ShardManager = Depends(get_shard_manager),
):
    """
    Fetch a user by their Snowflake ID (accepted as string).

    Snowflake IDs exceed JS Number.MAX_SAFE_INTEGER so we keep them as
    strings end-to-end. We convert to Python int here for bit operations.
    The shard is extracted in O(1) — no scatter-gather, no lookup table.
    """
    try:
        uid = int(user_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="user_id must be a valid integer.")

    shard_index = ShardRouter.route(uid)
    conn        = manager.get_connection(shard_index)
    row         = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")

    return UserResponse(
        **dict(row),
        shard_id=shard_index,
        id_breakdown=ShardRouter.decompose(uid),
    )


# ── GET /users/ ───────────────────────────────────────────────────────────────

@router.get("/", response_model=list[UserResponse])
def list_users(
    limit:  int = 50,
    offset: int = 0,
    manager: ShardManager = Depends(get_shard_manager),
):
    """
    List users across ALL shards.

    This is the one operation that touches every shard — a "scatter-gather"
    query. Results are merged and sorted by ID (which is time-sortable).

    In production you'd paginate per-shard or use a search index (Elasticsearch)
    for cross-shard queries. For this demo, we merge in Python.
    """
    all_users: list[UserResponse] = []

    for shard_index in ShardRouter.all_shards():
        conn = manager.get_connection(shard_index)
        rows = conn.execute("SELECT * FROM users WHERE is_active = 1").fetchall()
        for row in rows:
            uid = row["id"]
            all_users.append(UserResponse(
                **dict(row),
                shard_id=shard_index,
                id_breakdown=ShardRouter.decompose(uid),
            ))

    # Sort by Snowflake ID = chronological order (timestamp embedded in ID)
    all_users.sort(key=lambda u: int(u.id))
    return all_users[offset: offset + limit]


# ── DELETE /users/{user_id} ───────────────────────────────────────────────────

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    manager: ShardManager = Depends(get_shard_manager),
):
    """
    Soft-delete a user (sets is_active = 0).
    Accepts ID as string to avoid precision loss on 64-bit Snowflake IDs.
    """
    try:
        uid = int(user_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="user_id must be a valid integer.")

    shard_index = ShardRouter.route(uid)
    conn        = manager.get_connection(shard_index)
    cursor      = conn.execute(
        "UPDATE users SET is_active = 0 WHERE id = ?", (uid,)
    )
    conn.commit()

    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
