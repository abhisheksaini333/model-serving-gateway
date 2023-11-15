import asyncio
import time
import pytest
from gateway.admission import Admission
from gateway.coordination import TenantLimits
from gateway.contracts import GenerationRequest
from gateway.engine import Engine
from gateway.errors import GatewayError
from gateway.routing import Router
from gateway.store import Store
from test_engine import CountingBackend


def test_request_deadline_includes_coordinator_wait(tmp_path):
    class SlowCoordinator:
        async def reserve(self, *args):
            await asyncio.sleep(0.6)
            raise GatewayError("coordination_unavailable", "Unavailable")

    async def scenario():
        store = Store(tmp_path / "ledger.sqlite")
        engine = Engine(
            Router([CountingBackend()]), Admission(1, 1), SlowCoordinator(), store
        )
        request = GenerationRequest(model="flan-small", prompt="hello", timeout_ms=100)
        started = time.monotonic()
        with pytest.raises(GatewayError) as caught:
            await engine.submit("alpha", request, TenantLimits())
        assert caught.value.code == "deadline_exceeded"
        assert time.monotonic() - started < 0.4
        assert store.get("alpha", request.request_id)["state"] == "expired"
        assert not engine.jobs
        store.close()

    asyncio.run(scenario())
