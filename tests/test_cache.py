import asyncio
import os
import uuid
import pytest
from gateway.coordination import RedisCoordinator
from gateway.contracts import GenerationRequest
from gateway.identity import cache_key

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_REDIS_URL"), reason="Requires dedicated real Redis"
)


def test_cache_does_not_cross_tenants_or_preserve_request_identifiers():
    async def scenario():
        coordinator = RedisCoordinator(
            os.environ["TEST_REDIS_URL"], "cache-" + uuid.uuid4().hex
        )
        request = GenerationRequest(model="flan-small", prompt="private")
        alpha = cache_key("alpha", "original", request)
        beta = cache_key("beta", "original", request)
        value = {
            "text": "answer",
            "input_tokens": 4,
            "output_tokens": 2,
            "backend": "cpu-a",
            "finish_reason": "stop",
        }
        await coordinator.cache_put(alpha, value, ttl=60)
        assert await coordinator.cache_get(alpha) == value
        assert await coordinator.cache_get(beta) is None
        assert await coordinator.client.ttl(coordinator.namespace + ":" + alpha) > 0
        await coordinator.client.set(coordinator.namespace + ":" + alpha, "{broken")
        assert await coordinator.cache_get(alpha) is None
        await coordinator.close()

    asyncio.run(scenario())


def test_cache_rejects_partial_or_cancelled_results():
    async def scenario():
        coordinator = RedisCoordinator(
            os.environ["TEST_REDIS_URL"], "cache-" + uuid.uuid4().hex
        )
        with pytest.raises(ValueError):
            await coordinator.cache_put(
                "key", {"text": "partial", "finish_reason": "cancelled"}, 60
            )
        await coordinator.close()

    asyncio.run(scenario())
