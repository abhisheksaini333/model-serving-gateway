"""Non-reversible scoped request and cache identities."""
import hashlib
import json
from .contracts import GenerationRequest


def digest(payload: dict) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def fingerprint(request: GenerationRequest) -> str:
    return digest(request.dict(exclude={"request_id"}))


def cache_key(tenant: str, revision: str, request: GenerationRequest) -> str | None:
    if request.temperature != 0:
        return None
    return "generation:v1:" + digest(
        {
            "tenant": tenant,
            "revision": revision,
            "request": request.dict(exclude={"request_id", "timeout_ms"}),
        }
    )
