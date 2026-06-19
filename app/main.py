"""
main.py — FastAPI application entry point
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.db.shard_manager  import get_shard_manager, ShardManager
from app.models.user        import ShardStats
from app.routers            import users

STATIC_DIR = Path(__file__).parent / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    manager = get_shard_manager()
    print(f"✅ Initialized {len(manager._connections)} shard databases")
    yield
    manager.close_all()
    print("🔒 Shard connections closed")

app = FastAPI(
    title="❄️ Snowflake Sharding API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router, prefix="/users", tags=["Users"])

@app.get("/shards/stats", response_model=list[ShardStats], tags=["Shards"])
def shard_stats(manager: ShardManager = Depends(get_shard_manager)):
    return manager.get_shard_stats()

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "shards": 8}

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", include_in_schema=False)
def serve_frontend():
    return FileResponse(str(STATIC_DIR / "index.html"))
