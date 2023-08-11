"""Redis admission fails closed; rejected attempts never invoke inference."""
import hashlib
import math
import re
from dataclasses import dataclass
from redis import asyncio as redis
from redis.exceptions import RedisError
from .errors import GatewayError
from .quota_scripts import RESERVE, SETTLE


@dataclass(frozen=True)
class TenantLimits:
    requests: int = 60
    concurrent: int = 4
    output_tokens: int = 4096
    window_seconds: int = 60

    def __post_init__(self):
        if any(type(value) is not int or value < 1 for value in self.__dict__.values()):
            raise ValueError("positive integer tenant limits required")


@dataclass(frozen=True)
class Reservation:
    keys: tuple[str, str]
    identity: str
    window: str
    tokens: int


class RedisCoordinator:
    def __init__(self, url: str, namespace="serving-gateway"):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", namespace):
            raise ValueError("invalid Redis namespace")
        self.namespace = namespace
        self.client = redis.from_url(
            url,
            decode_responses=True,
            socket_timeout=1,
            socket_connect_timeout=1,
            max_connections=32,
        )

    def tenant_keys(self, tenant):
        identity = hashlib.sha256(tenant.encode()).hexdigest()[:32]
        base = self.namespace + ":{" + identity + "}"
        return base + ":quota", base + ":active"

    async def execute(self, operation, *args, **kwargs):
        try:
            return await operation(*args, **kwargs)
        except (RedisError, OSError) as error:
            raise GatewayError(
                "coordination_unavailable", "Admission storage is unavailable."
            ) from error

    async def reserve(
        self,
        tenant: str,
        request_id: str,
        tokens: int,
        timeout_ms: int,
        limits: TenantLimits,
    ) -> Reservation:
        if tokens < 1 or not 100 <= timeout_ms <= 120000:
            raise ValueError("bounded reservation required")
        keys = self.tenant_keys(tenant)
        result = await self.execute(
            self.client.eval,
            RESERVE,
            2,
            *keys,
            request_id,
            tokens,
            limits.requests,
            limits.concurrent,
            limits.output_tokens,
            limits.window_seconds,
            math.ceil(timeout_ms / 1000) + 30
        )
        if result[0] != "ok":
            raise GatewayError(result[0], "Tenant admission limit reached.", 429)
        return Reservation(keys, request_id, result[1], tokens)

    async def settle(self, reservation: Reservation, output_tokens: int):
        if not 0 <= output_tokens <= reservation.tokens:
            raise ValueError("actual tokens exceed the reservation")
        return await self.execute(
            self.client.eval,
            SETTLE,
            2,
            *reservation.keys,
            reservation.identity,
            reservation.window,
            reservation.tokens - output_tokens
        )

    async def healthy(self):
        return await self.execute(self.client.ping)

    async def close(self):
        await self.client.close()
