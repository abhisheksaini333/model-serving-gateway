import asyncio
import os
import uuid
import pytest
from gateway.admission import Admission
from gateway.coordination import RedisCoordinator, TenantLimits
from gateway.contracts import GenerationRequest
from gateway.engine import Engine
from gateway.errors import GatewayError
from gateway.routing import Router
from gateway.store import Store
from test_engine import CountingBackend

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_REDIS_URL"), reason="Requires dedicated Redis"
)


def test_ledger_failure_withholds_success_and_completes_all_cleanup(tmp_path):
    class FailedLedger(Store):
        def finish(self, *args, **kwargs):
            raise OSError("private database location")

    async def scenario():
        coordinator = RedisCoordinator(
            os.environ["TEST_REDIS_URL"], "final-" + uuid.uuid4().hex
        )
        store = FailedLedger(tmp_path / "ledger.sqlite")
        engine = Engine(
            Router([CountingBackend()]),
            Admission(1, 2),
            coordinator,
            store,
            cache_ttl=0,
        )
        job = await engine.submit(
            "alpha",
            GenerationRequest(model="flan-small", prompt="hello"),
            TenantLimits(),
        )
        await asyncio.wait_for(job.task, 2)
        events = [event async for event in job.events()]
        assert not any(event["type"] == "result" for event in events)
        assert events[-1]["error"]["code"] == "ledger_unavailable"
        assert "private" not in str(events)
        assert not engine.jobs and engine.admission.active == 0
        assert await coordinator.client.zcard(coordinator.tenant_keys("alpha")[1]) == 0
        assert not engine.ledger_healthy
        with pytest.raises(GatewayError) as caught:
            await engine.submit(
                "alpha",
                GenerationRequest(model="flan-small", prompt="hello"),
                TenantLimits(),
            )
        assert caught.value.code == "ledger_unavailable"
        await engine.close()
        store.close()

    asyncio.run(scenario())


def test_unexpected_backend_exception_becomes_sanitized_terminal_error(tmp_path):
    class BrokenBackend(CountingBackend):
        async def stream(self, request, cancel):
            raise RuntimeError("credential=private")
            yield

    async def scenario():
        coordinator = RedisCoordinator(
            os.environ["TEST_REDIS_URL"], "broken-" + uuid.uuid4().hex
        )
        store = Store(tmp_path / "ledger.sqlite")
        engine = Engine(
            Router([BrokenBackend()]), Admission(1, 2), coordinator, store, cache_ttl=0
        )
        job = await engine.submit(
            "alpha",
            GenerationRequest(model="flan-small", prompt="hello"),
            TenantLimits(),
        )
        events = [event async for event in job.events()]
        await job.task
        assert events[-1]["error"]["code"] == "backend_failed"
        assert "private" not in str(events)
        assert not engine.jobs and engine.admission.active == 0
        await engine.close()
        store.close()

    asyncio.run(scenario())
