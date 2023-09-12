"""Explicit bounded environment configuration without credential representations."""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from .auth import Authenticator
from .coordination import TenantLimits


@dataclass(frozen=True)
class Settings:
    model_path: Path
    database: Path
    redis_url: str = field(repr=False)
    auth: Authenticator = field(repr=False)
    queue_size: int = 4
    cache_ttl: int = 300
    namespace: str = "serving-gateway"

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        try:
            model_path = Path(env["GATEWAY_MODEL_PATH"])
            tenants = json.loads(env["GATEWAY_TENANTS_JSON"])
            credentials = {
                tenant: (config["api_key"], TenantLimits(**config.get("limits", {})))
                for tenant, config in tenants.items()
            }
            auth = Authenticator(credentials, env["GATEWAY_OPERATOR_KEY"])
            queue_size = int(env.get("GATEWAY_QUEUE_SIZE", "4"))
            cache_ttl = int(env.get("GATEWAY_CACHE_TTL", "300"))
            redis_url = env.get("GATEWAY_REDIS_URL", "redis://127.0.0.1:56383/0")
            if not 0 <= queue_size <= 64 or not 0 <= cache_ttl <= 3600:
                raise ValueError("queue/cache limits out of range")
            if urlparse(redis_url).scheme not in {"redis", "rediss"}:
                raise ValueError("Redis URL must use redis or rediss")
            if not model_path.is_dir():
                raise ValueError("model directory missing")
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise ValueError(
                "Invalid gateway configuration; check credentials, model path and bounded limits."
            ) from error
        return cls(
            model_path,
            Path(env.get("GATEWAY_DATABASE", "var/gateway.sqlite")),
            redis_url,
            auth,
            queue_size,
            cache_ttl,
            env.get("GATEWAY_NAMESPACE", "serving-gateway"),
        )
