import asyncio,threading
import pytest
from gateway.routing import Router
from gateway.registry import BackendSpec
from gateway.contracts import GenerationRequest

class BrokenStream:
    def __aiter__(self): return self
    async def __anext__(self): raise StopAsyncIteration
    async def aclose(self): raise RuntimeError("close failed")
class Backend:
    spec=BackendSpec("b","m","r")
    def stream(self,*args): return BrokenStream()

def test_stream_cleanup_failure_releases_capacity():
    async def scenario():
        router=Router([Backend()])
        with pytest.raises(Exception):
            async for _ in router.stream(GenerationRequest(model="m",prompt="x"),threading.Event()): pass
        assert router.active["b"] == 0
        assert not router.breakers["b"].probe
    asyncio.run(scenario())
