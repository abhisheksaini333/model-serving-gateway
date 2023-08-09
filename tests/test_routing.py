import asyncio
import threading
import pytest
from gateway.backends import GenerationEvent
from gateway.contracts import GenerationRequest, Usage
from gateway.errors import GatewayError
from gateway.registry import BackendSpec
from gateway.routing import Router


class ScriptedBackend:
    def __init__(self, name, events):
        self.spec = BackendSpec(name, "flan-small", "original")
        self.events = events
        self.calls = 0

    async def stream(self, request, cancel):
        self.calls += 1
        for event in self.events:
            if isinstance(event, Exception):
                raise event
            yield event


def test_failure_before_output_falls_back_but_partial_text_never_replays():
    async def scenario(partial):
        error = GatewayError("backend_failed", "Failed")
        first = ScriptedBackend(
            "cpu-a", ([GenerationEvent(text="partial")] if partial else []) + [error]
        )
        second = ScriptedBackend(
            "cpu-b",
            [
                GenerationEvent(text="answer"),
                GenerationEvent(
                    usage=Usage(input_tokens=2, output_tokens=1), finish_reason="stop"
                ),
            ],
        )
        router = Router([first, second], failure_threshold=1)
        output = []
        try:
            async for event in router.stream(
                GenerationRequest(model="flan-small", prompt="hello"), threading.Event()
            ):
                output.append(event.event.text)
        except GatewayError:
            assert partial
        assert "".join(output) == ("partial" if partial else "answer")
        assert second.calls == (0 if partial else 1)
        assert all(item["active"] == 0 for item in router.snapshot())
        assert router.snapshot()[0]["circuit"] == "open"

    asyncio.run(scenario(False))
    asyncio.run(scenario(True))


def test_drained_backend_is_skipped_and_invalid_request_does_not_open_circuit():
    async def scenario():
        first = ScriptedBackend("cpu-a", [GenerationEvent(text="bad")])
        second = ScriptedBackend(
            "cpu-b", [GatewayError("context_limit", "Too long", 422)]
        )
        router = Router([first, second], failure_threshold=1)
        router.set_mode("cpu-a", "draining")
        with pytest.raises(GatewayError) as error:
            async for _ in router.stream(
                GenerationRequest(model="flan-small", prompt="hello"), threading.Event()
            ):
                pass
        assert error.value.code == "context_limit"
        assert first.calls == 0
        assert router.snapshot()[1]["circuit"] == "closed"
        with pytest.raises(GatewayError):
            router.set_mode("unknown", "enabled")

    asyncio.run(scenario())
