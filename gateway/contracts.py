"""Public contracts; tenant identity is resolved from credentials, never the body."""
from uuid import uuid4
from pydantic import BaseModel, Field, conint, validator


class GenerationRequest(BaseModel):
    model: str = Field(..., regex=r"^[a-z][a-z0-9-]{0,63}$")
    prompt: str = Field(..., min_length=1, max_length=16384)
    request_id: str = Field(
        default_factory=lambda: str(uuid4()), regex=r"^[A-Za-z0-9_-]{1,80}$"
    )
    max_new_tokens: conint(strict=True, ge=1, le=512) = 64
    timeout_ms: conint(strict=True, ge=100, le=120000) = 30000
    temperature: float = Field(0, ge=0, le=2, allow_inf_nan=False)

    @validator("prompt")
    def nonblank_prompt(cls, value):
        if not value.strip():
            raise ValueError("prompt must contain text")
        return value

    class Config:
        extra = "forbid"


class Usage(BaseModel):
    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)


class GenerationResponse(BaseModel):
    request_id: str
    model: str
    text: str
    finish_reason: str
    usage: Usage
    cached: bool = False
    backend: str
    latency_ms: float
    ttft_ms: float | None = None
