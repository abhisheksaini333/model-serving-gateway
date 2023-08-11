import asyncio
import os
import uuid
import pytest
from gateway.coordination import RedisCoordinator, TenantLimits
from gateway.errors import GatewayError

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_REDIS_URL"), reason="Requires dedicated real Redis"
)


def test_atomic_tenant_quota_and_idempotent_settlement():
    async def scenario():
        coordinator = RedisCoordinator(
            os.environ["TEST_REDIS_URL"], "test-" + uuid.uuid4().hex
        )
        limits = TenantLimits(
            requests=10, concurrent=1, output_tokens=20, window_seconds=60
        )
        first = await coordinator.reserve("alpha", "one", 10, 1000, limits)
        with pytest.raises(GatewayError) as error:
            await coordinator.reserve("alpha", "two", 10, 1000, limits)
        assert error.value.code == "tenant_concurrency"
        other = await coordinator.reserve("beta", "one", 10, 1000, limits)
        await coordinator.settle(first, 3)
        await coordinator.settle(first, 3)
        second = await coordinator.reserve("alpha", "two", 17, 1000, limits)
        await coordinator.settle(second, 17)
        with pytest.raises(GatewayError) as error:
            await coordinator.reserve("alpha", "three", 1, 1000, limits)
        assert error.value.code == "token_quota"
        await coordinator.settle(other, 0)
        await coordinator.close()

    asyncio.run(scenario())


def test_concurrent_reservations_cannot_overspend_request_window():
    async def scenario():
        coordinator = RedisCoordinator(
            os.environ["TEST_REDIS_URL"], "test-" + uuid.uuid4().hex
        )
        limits = TenantLimits(
            requests=2, concurrent=10, output_tokens=100, window_seconds=60
        )
        results = await asyncio.gather(
            *[coordinator.reserve("alpha", str(i), 1, 1000, limits) for i in range(12)],
            return_exceptions=True
        )
        accepted = [result for result in results if not isinstance(result, Exception)]
        assert len(accepted) == 2
        assert all(
            result.code == "request_quota"
            for result in results
            if isinstance(result, Exception)
        )
        for lease in accepted:
            await coordinator.settle(lease, 1)
        await coordinator.close()

    asyncio.run(scenario())


def test_unavailable_redis_fails_closed_without_exposing_connection_details():
    async def scenario():
        coordinator = RedisCoordinator("redis://127.0.0.1:1", "failure")
        with pytest.raises(GatewayError) as error:
            await coordinator.reserve("alpha", "one", 1, 1000, TenantLimits())
        assert error.value.code == "coordination_unavailable"
        assert "127.0.0.1" not in str(error.value)
        await coordinator.close()

    asyncio.run(scenario())
