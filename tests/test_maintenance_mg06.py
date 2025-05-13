import asyncio,threading
import pytest
from gateway.routing import Router
from gateway.registry import BackendSpec
from gateway.contracts import GenerationRequest
from gateway.backends import GenerationEvent
from gateway.errors import GatewayError

@pytest.mark.parametrize("events", [[],[GenerationEvent(text="partial")]])
def test_missing_terminal_usage_is_backend_failure(events):
    class Backend:
        spec=BackendSpec("b","m","r")
        async def stream(self,*args):
            for event in events: yield event
    async def scenario():
        router=Router([Backend()])
        with pytest.raises(GatewayError) as caught:
            async for _ in router.stream(GenerationRequest(model="m",prompt="x"),threading.Event()): pass
        assert caught.value.code == "backend_failed"
        assert router.active["b"] == 0
    asyncio.run(scenario())
