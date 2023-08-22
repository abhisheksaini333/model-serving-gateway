"""Only complete bounded deterministic responses may enter Redis cache."""
from typing import Literal
from pydantic import BaseModel, Field


class CacheEntry(BaseModel):
    text: str = Field(..., max_length=65536)
    input_tokens: int = Field(..., ge=0, le=16384)
    output_tokens: int = Field(..., ge=0, le=512)
    backend: str = Field(..., regex=r"^[a-z][a-z0-9-]{0,63}$")
    finish_reason: Literal["stop", "length"]

    class Config:
        extra = "forbid"
