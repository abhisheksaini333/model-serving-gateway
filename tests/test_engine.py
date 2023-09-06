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


class LongBackend:
    spec = BackendSpec("cpu-a", "flan-small", "original")

    def __init__(self):
        self.running = False

    async def stream(self, request, cancel):
        self.running = True
        count = 0
        try:
            while count < request.max_new_tokens and not cancel.is_set():
                await asyncio.sleep(0.01)
                count += 1
                yield GenerationEvent(text="word ")
            yield GenerationEvent(
                usage=Usage(input_tokens=3, output_tokens=count),
                finish_reason="cancelled" if cancel.is_set() else "length",
            )
        finally:
            self.running = False


def test_running_cancel_and_deadline_release_worker_and_preserve_partial_usage(
    tmp_path,
):
    async def scenario():
        backend = LongBackend()
        coordinator = RedisCoordinator(
            os.environ["TEST_REDIS_URL"], "cancel-" + uuid.uuid4().hex
        )
        store = Store(tmp_path / "ledger.sqlite")
        engine = Engine(
            Router([backend]), Admission(1, 2), coordinator, store, cache_ttl=0
        )
        first = await engine.submit(
            "alpha",
            GenerationRequest(model="flan-small", prompt="hello", request_id="cancel"),
            TenantLimits(),
        )
        assert (await first.queue.get())["type"] == "token"
        assert engine.cancel("beta", "cancel") is False
        assert engine.cancel("alpha", "cancel") is True
        await first.task
        record = store.get("alpha", "cancel")
        assert record["state"] == "cancelled"
        assert record["output_tokens"] > 0
        assert not backend.running and engine.admission.active == 0
        second = await engine.submit(
            "alpha",
            GenerationRequest(
                model="flan-small", prompt="hello", request_id="expire", timeout_ms=100
            ),
            TenantLimits(),
        )
        events = [event async for event in second.events()]
        assert events[-1]["error"]["code"] == "deadline_exceeded"
        assert store.get("alpha", "expire")["state"] == "expired"
        assert not backend.running and engine.admission.active == 0
        await engine.close()
        store.close()

    asyncio.run(scenario())


def test_queued_cancellation_even_before_runner_starts_cleans_reservation(tmp_path):
    async def scenario():
        coordinator = RedisCoordinator(
            os.environ["TEST_REDIS_URL"], "queued-" + uuid.uuid4().hex
        )
        store = Store(tmp_path / "ledger.sqlite")
        engine = Engine(
            Router([LongBackend()]), Admission(1, 2), coordinator, store, cache_ttl=0
        )
        job = await engine.submit(
            "alpha",
            GenerationRequest(model="flan-small", prompt="hello", request_id="queued"),
            TenantLimits(),
        )
        engine.cancel("alpha", "queued")
        await job.task
        assert not engine.jobs
        assert engine.admission.active == 0
        assert store.get("alpha", "queued")["state"] == "cancelled"
        assert await coordinator.client.zcard(coordinator.tenant_keys("alpha")[1]) == 0
        await engine.close()
        store.close()

    asyncio.run(scenario())
