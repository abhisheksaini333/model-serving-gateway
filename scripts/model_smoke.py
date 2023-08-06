"""Measure the actual local CPU adapter; no synthetic adapter is used here."""
import argparse
import asyncio
import json
import platform
import threading
import time
from pathlib import Path
from gateway.artifacts import verify_artifacts
from gateway.backends import LocalTransformersBackend
from gateway.contracts import GenerationRequest
from gateway.registry import BackendSpec


async def measure(backend, prompt, cancel_after_first=False):
    cancel = threading.Event()
    started = time.perf_counter()
    chunks, ttft, final = [], None, None
    active_at_cancel = None
    async for event in backend.stream(
        GenerationRequest(model="flan-small", prompt=prompt, max_new_tokens=128), cancel
    ):
        if event.text:
            if ttft is None:
                ttft = time.perf_counter() - started
            chunks.append(event.text)
            if cancel_after_first and not cancel.is_set():
                active_at_cancel = backend.active_workers
                cancel.set()
        if event.usage:
            final = event
    elapsed = time.perf_counter() - started
    return dict(
        prompt=prompt,
        text="".join(chunks),
        chunks=len(chunks),
        latency_ms=elapsed * 1000,
        ttft_ms=ttft * 1000 if ttft else None,
        usage=final.usage.dict(),
        finish_reason=final.finish_reason,
        active_workers_after=backend.active_workers,
        active_workers_at_cancel=active_at_cancel,
        tokens_per_second=final.usage.output_tokens / elapsed,
    )


async def main(args):
    manifest = json.loads(Path("evidence/model-artifacts.json").read_text())
    verify_artifacts(args.model_path, manifest)
    spec = BackendSpec("cpu-a", "flan-small", manifest[0]["revision"])
    backend = LocalTransformersBackend.load(spec, args.model_path)
    normal = await measure(
        backend,
        "Answer with the name only. Mira owns the Atlas service. Who owns Atlas?",
    )
    cancelled = await measure(
        backend,
        "Translate English to German: The little girl walks along the river every morning with her grandfather. They watch the birds and talk about the flowers in the garden.",
        True,
    )
    result = dict(
        adapter="actual-transformers-cpu",
        model="google/flan-t5-small",
        revision=spec.revision,
        cpu_threads=2,
        platform=platform.platform(),
        normal=normal,
        cancelled=cancelled,
    )
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    assert normal["text"] and normal["active_workers_after"] == 0
    assert (
        cancelled["finish_reason"] == "cancelled"
        and cancelled["active_workers_after"] == 0
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--output", default="evidence/model-smoke.json")
    asyncio.run(main(parser.parse_args()))
