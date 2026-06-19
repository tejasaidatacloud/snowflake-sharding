"""
user.py — Pydantic schemas for the User entity

WHY id IS A STRING
------------------
Snowflake IDs are 64-bit integers that exceed JavaScript's Number.MAX_SAFE_INTEGER
(2^53 - 1 = 9,007,199,254,740,991). A 64-bit Snowflake like 326141875058638850
gets silently rounded by JSON.parse() in the browser, making lookups fail even
though the user exists. Returning the ID as a string sidesteps this entirely —
the frontend passes the raw string straight back to the API URL without ever
converting it to a JS number.
"""

from pydantic import BaseModel, EmailStr, Field, field_serializer
from typing import Optional


class UserCreate(BaseModel):
    username:  str            = Field(..., min_length=3, max_length=30,  examples=["alice_99"])
    email:     EmailStr       = Field(...,                                examples=["alice@example.com"])
    full_name: Optional[str]  = Field(None, max_length=100,              examples=["Alice Smith"])
    region:    Optional[str]  = Field(None, max_length=20,               examples=["us-east"])


class UserInDB(BaseModel):
    id:         int
    username:   str
    email:      str
    full_name:  Optional[str]
    region:     Optional[str]
    created_at: str
    is_active:  bool

    model_config = {"from_attributes": True}

    # Serialize id as string so JS never loses precision
    @field_serializer("id")
    def serialize_id(self, v: int) -> str:
        return str(v)


class UserResponse(UserInDB):
    shard_id:     int
    id_breakdown: dict   # timestamp_ms, shard_id, sequence


class ShardStats(BaseModel):
    shard_id:    int
    user_count:  int
    db_size_kb:  float
    db_file:     str
