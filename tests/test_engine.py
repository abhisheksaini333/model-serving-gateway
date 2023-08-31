import asyncio
import os
import uuid
import pytest
from gateway.admission import Admission
from gateway.coordination import RedisCoordinator, TenantLimits
from gateway.contracts import GenerationRequest, Usage
from gateway.backends import GenerationEvent
from gateway.registry import BackendSpec
from gateway.routing import Router
from gateway.store import Store
from gateway.engine import Engine

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_REDIS_URL"), reason="Requires dedicated Redis"
)


class CountingBackend:
    spec = BackendSpec("cpu-a", "flan-small", "original")

    def __init__(self):
        self.calls = 0

    async def stream(self, request, cancel):
        self.calls += 1
        yield GenerationEvent(text="answer")
        yield GenerationEvent(
            usage=Usage(input_tokens=3, output_tokens=1), finish_reason="stop"
        )


def test_complete_run_accounting_cache_hit_and_tenant_isolation(tmp_path):
    async def scenario():
        backend = CountingBackend()
        coordinator = RedisCoordinator(
            os.environ["TEST_REDIS_URL"], "engine-" + uuid.uuid4().hex
        )
        store = Store(tmp_path / "ledger.sqlite")
        engine = Engine(Router([backend]), Admission(1, 2), coordinator, store)

        async def run(tenant, identity):
            job = await engine.submit(
                tenant,
                GenerationRequest(
                    model="flan-small", prompt="hello", request_id=identity
                ),
                TenantLimits(),
            )
            events = [event async for event in job.events()]
            assert events[-1]["type"] == "result"
            return events[-1]["response"]

        first = await run("alpha", "one")
        second = await run("alpha", "two")
        third = await run("beta", "one")
        assert not first["cached"] and second["cached"] and not third["cached"]
        assert second["usage"]["output_tokens"] == 0
        assert backend.calls == 2
        assert store.get("alpha", "one")["state"] == "completed"
        assert store.get("alpha", "one")["output_tokens"] == 1
        assert engine.admission.snapshot()["active"] == 0
        await engine.close()
        store.close()

    asyncio.run(scenario())
