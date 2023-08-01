"""Actual CPU token streaming with cooperative cancellation and worker cleanup."""
import asyncio
import queue
import threading
from dataclasses import dataclass
from typing import AsyncIterator
from .contracts import GenerationRequest, Usage
from .errors import GatewayError
from .registry import BackendSpec


@dataclass(frozen=True)
class GenerationEvent:
    text: str = ""
    usage: Usage | None = None
    finish_reason: str | None = None


class LocalTransformersBackend:
    def __init__(self, spec: BackendSpec, tokenizer, model):
        self.spec = spec
        self.tokenizer = tokenizer
        self.model = model
        self._workers: set[threading.Thread] = set()
        self._lock = threading.Lock()

    @classmethod
    def load(cls, spec: BackendSpec, path: str, threads: int = 2):
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        torch.set_num_threads(threads)
        tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
        model = AutoModelForSeq2SeqLM.from_pretrained(path, local_files_only=True)
        model.eval()
        return cls(spec, tokenizer, model)

    @property
    def active_workers(self) -> int:
        with self._lock:
            return sum(worker.is_alive() for worker in self._workers)

    async def stream(
        self, request: GenerationRequest, cancel: threading.Event
    ) -> AsyncIterator[GenerationEvent]:
        import torch
        from transformers import (
            StoppingCriteria,
            StoppingCriteriaList,
            TextIteratorStreamer,
        )

        class Cancelled(StoppingCriteria):
            def __call__(self, input_ids, scores, **kwargs):
                return cancel.is_set()

        inputs = self.tokenizer(request.prompt, return_tensors="pt", truncation=False)
        input_tokens = int(inputs["input_ids"].shape[-1])
        if input_tokens > self.spec.max_input_tokens:
            raise GatewayError(
                "context_limit", "Prompt exceeds the model token limit.", 422
            )
        if request.max_new_tokens > self.spec.max_output_tokens:
            raise GatewayError(
                "output_limit", "Output exceeds the model token limit.", 422
            )
        streamer = TextIteratorStreamer(
            self.tokenizer, skip_prompt=True, skip_special_tokens=True, timeout=0.05
        )
        result = {}
        errors = []

        def generate():
            try:
                options = dict(
                    inputs,
                    streamer=streamer,
                    max_new_tokens=request.max_new_tokens,
                    do_sample=request.temperature > 0,
                    stopping_criteria=StoppingCriteriaList([Cancelled()]),
                )
                if request.temperature > 0:
                    options["temperature"] = request.temperature
                with torch.inference_mode():
                    output = self.model.generate(**options)
                result["tokens"] = max(0, int(output.shape[-1]) - 1)
            except Exception:
                errors.append(True)
                streamer.end()

        worker = threading.Thread(
            target=generate, name="generation-" + self.spec.name, daemon=True
        )
        with self._lock:
            self._workers.add(worker)
        worker.start()
        try:
            while True:
                try:
                    text = await asyncio.to_thread(streamer.text_queue.get, True, 0.05)
                except queue.Empty:
                    if not worker.is_alive():
                        break
                    continue
                if text is streamer.stop_signal:
                    break
                if text:
                    yield GenerationEvent(text=text)
            await asyncio.to_thread(worker.join)
            if errors:
                raise GatewayError("backend_failed", "The inference backend failed.")
            tokens = result.get("tokens", 0)
            reason = (
                "cancelled"
                if cancel.is_set()
                else ("length" if tokens >= request.max_new_tokens else "stop")
            )
            yield GenerationEvent(
                usage=Usage(input_tokens=input_tokens, output_tokens=tokens),
                finish_reason=reason,
            )
        finally:
            cancel.set()
            await asyncio.to_thread(worker.join)
            with self._lock:
                self._workers.discard(worker)
