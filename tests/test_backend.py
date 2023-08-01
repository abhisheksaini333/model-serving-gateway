import asyncio
import threading
import time
import pytest
from gateway.backends import LocalTransformersBackend
from gateway.contracts import GenerationRequest
from gateway.registry import BackendSpec
from gateway.errors import GatewayError


class TinyTokenizer:
    def __call__(self, prompt, **kwargs):
        import torch

        return {"input_ids": torch.tensor([[1, 2, 3]])}

    def decode(self, tokens, **kwargs):
        return "".join("word " for token in tokens if token != 0)


class ControlledModel:
    def __init__(self, first_token=None):
        self.first_token = first_token

    def generate(self, **options):
        import torch

        stream = options["streamer"]
        stream.put(torch.tensor([[0]]))
        tokens = [0]
        for _ in range(options["max_new_tokens"]):
            time.sleep(0.005)
            tokens.append(1)
            stream.put(torch.tensor([1]))
            if len(tokens) == 2 and self.first_token is not None:
                self.first_token.wait(2)
            if options["stopping_criteria"](torch.tensor([tokens]), None):
                break
        stream.end()
        return torch.tensor([tokens])


def adapter(model=None):
    return LocalTransformersBackend(
        BackendSpec("cpu-a", "flan-small", "original"),
        TinyTokenizer(),
        model or ControlledModel(),
    )


def test_streams_before_completion_and_reports_actual_token_counts():
    async def scenario():
        release = threading.Event()
        backend = adapter(ControlledModel(release))
        events = []
        async for event in backend.stream(
            GenerationRequest(model="flan-small", prompt="hi", max_new_tokens=8),
            threading.Event(),
        ):
            events.append(event)
            if event.text and not release.is_set():
                assert backend.active_workers == 1
                release.set()
        assert "".join(event.text for event in events) == "word " * 8
        assert events[-1].usage.output_tokens == 8
        assert events[-1].usage.input_tokens == 3
        assert backend.active_workers == 0

    asyncio.run(scenario())


def test_cancellation_joins_generator_before_returning_capacity():
    async def scenario():
        backend = adapter()
        cancel = threading.Event()
        events = []
        async for event in backend.stream(
            GenerationRequest(model="flan-small", prompt="hi", max_new_tokens=100),
            cancel,
        ):
            events.append(event)
            if event.text:
                cancel.set()
        assert events[-1].finish_reason == "cancelled"
        assert events[-1].usage.output_tokens < 100
        assert backend.active_workers == 0

    asyncio.run(scenario())


def test_generator_exception_is_sanitized_and_does_not_hang():
    class BrokenModel:
        def generate(self, **kwargs):
            raise RuntimeError("secret credential and prompt")

    async def scenario():
        backend = adapter(BrokenModel())
        with pytest.raises(GatewayError) as caught:
            async for _ in backend.stream(
                GenerationRequest(model="flan-small", prompt="secret"),
                threading.Event(),
            ):
                pass
        assert caught.value.code == "backend_failed"
        assert "secret" not in str(caught.value)
        assert backend.active_workers == 0

    asyncio.run(scenario())
