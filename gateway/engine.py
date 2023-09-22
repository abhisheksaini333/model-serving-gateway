"""Request lifecycle joins admission, routing, cache and durable usage."""
import asyncio
import threading
import time
from .contracts import GenerationRequest, GenerationResponse, Usage
from .coordination import TenantLimits
from .errors import GatewayError
from .identity import fingerprint, cache_key
from .metrics import Metrics


class Job:
    def __init__(self, tenant: str, request: GenerationRequest):
        self.tenant = tenant
        self.request = request
        self.started = time.monotonic()
        self.deadline = self.started + request.timeout_ms / 1000
        self.stop = threading.Event()
        self.cancelled = asyncio.Event()
        self.cancel_reason = "cancelled"
        self.queue = asyncio.Queue(maxsize=1024)
        self.task = None
        self.phase = "queued"

    def cancel(self, reason="cancelled"):
        self.cancel_reason = reason
        self.stop.set()
        self.cancelled.set()

    def raise_if_cancelled(self):
        if self.stop.is_set():
            status = 504 if self.cancel_reason == "deadline_exceeded" else 499
            raise GatewayError(
                self.cancel_reason,
                "Request deadline expired."
                if status == 504
                else "Request was cancelled.",
                status,
            )

    async def events(self):
        while True:
            event = await self.queue.get()
            if event is None:
                return
            yield event


class Engine:
    def __init__(self, router, admission, coordinator, store, cache_ttl=300):
        self.router = router
        self.admission = admission
        self.coordinator = coordinator
        self.store = store
        self.cache_ttl = cache_ttl
        self.jobs = {}
        self.settlement_failures = 0
        self.metrics = Metrics(admission)

    async def submit(
        self, tenant: str, request: GenerationRequest, limits: TenantLimits
    ):
        specs = self.router.registry.for_model(request.model)
        job = Job(tenant, request)
        self.store.create(tenant, request.request_id, fingerprint(request))
        try:
            reservation = await self.coordinator.reserve(
                tenant,
                request.request_id,
                request.max_new_tokens,
                request.timeout_ms,
                limits,
            )
        except GatewayError as error:
            self.store.finish(
                tenant, request.request_id, "failed", error_code=error.code
            )
            raise
        key = cache_key(tenant, specs[0].revision, request) if self.cache_ttl else None
        identity = (tenant, request.request_id)
        self.jobs[identity] = job
        job.task = asyncio.create_task(self._run(job, reservation, key))
        return job

    def cancel(self, tenant: str, request_id: str) -> bool:
        job = self.jobs.get((tenant, request_id))
        if job is None:
            return False
        job.cancel()
        return True

    async def _acquire(self, job):
        waiting = asyncio.create_task(self.admission.acquire(job.tenant, job.deadline))
        cancelled = asyncio.create_task(job.cancelled.wait())
        try:
            await asyncio.wait(
                {waiting, cancelled}, return_when=asyncio.FIRST_COMPLETED
            )
            if waiting.done() and not waiting.cancelled():
                lease = waiting.result()
                if job.stop.is_set():
                    await lease.release()
                    job.raise_if_cancelled()
                return lease
            waiting.cancel()
            await asyncio.gather(waiting, return_exceptions=True)
            job.raise_if_cancelled()
        finally:
            cancelled.cancel()
            await asyncio.gather(cancelled, return_exceptions=True)

    async def _run(self, job, reservation, key):
        request = job.request
        lease = None
        stream = None
        usage = Usage(input_tokens=0, output_tokens=0)
        actual_tokens = reservation.tokens
        text, backend, ttft = "", "", None
        state, error_code = "failed", None
        cached = False
        timer = asyncio.get_running_loop().call_at(
            job.deadline, job.cancel, "deadline_exceeded"
        )
        try:
            job.raise_if_cancelled()
            entry = await self.coordinator.cache_get(key) if key else None
            job.raise_if_cancelled()
            if entry is not None:
                cached = True
                text, backend, reason = (
                    entry["text"],
                    entry["backend"],
                    entry["finish_reason"],
                )
                actual_tokens = 0
                job.queue.put_nowait(
                    {"type": "token", "text": text, "request_id": request.request_id}
                )
            else:
                lease = await self._acquire(job)
                job.phase = "running"
                self.store.start(job.tenant, request.request_id, "pending")
                stream = self.router.stream(request, job.stop)
                pieces = 0
                final = None
                async for routed in stream:
                    backend = routed.backend
                    event = routed.event
                    if event.text:
                        pieces += 1
                        text += event.text
                        if len(text) > 65536 or pieces > 512:
                            raise GatewayError(
                                "backend_failed",
                                "Backend output exceeded the bounded response.",
                            )
                        if ttft is None:
                            ttft = (time.monotonic() - job.started) * 1000
                        job.queue.put_nowait(
                            {
                                "type": "token",
                                "text": event.text,
                                "request_id": request.request_id,
                            }
                        )
                    if event.usage is not None:
                        final = event
                if final is None:
                    raise GatewayError(
                        "backend_failed", "Backend did not return final usage."
                    )
                usage, reason = final.usage, final.finish_reason
                actual_tokens = usage.output_tokens
                job.raise_if_cancelled()
                if key and reason in {"stop", "length"}:
                    await self.coordinator.cache_put(
                        key,
                        dict(
                            text=text,
                            backend=backend,
                            input_tokens=usage.input_tokens,
                            output_tokens=usage.output_tokens,
                            finish_reason=reason,
                        ),
                        self.cache_ttl,
                    )
            job.raise_if_cancelled()
            state = "completed"
            response = GenerationResponse(
                request_id=request.request_id,
                model=request.model,
                text=text,
                finish_reason=reason,
                usage=usage,
                cached=cached,
                backend=backend,
                latency_ms=(time.monotonic() - job.started) * 1000,
                ttft_ms=ttft,
            )
            job.queue.put_nowait({"type": "result", "response": response.dict()})
        except GatewayError as error:
            error_code = error.code
            state = (
                "expired"
                if error.code == "deadline_exceeded"
                else ("cancelled" if error.code == "cancelled" else "failed")
            )
            job.queue.put_nowait(
                {"type": "error", **error.payload(), "status": error.status}
            )
        except asyncio.CancelledError:
            state, error_code = "cancelled", "cancelled"
            job.stop.set()
        finally:
            timer.cancel()
            if stream is not None:
                await stream.aclose()
            if lease is not None:
                await lease.release()
            self.store.finish(
                job.tenant,
                request.request_id,
                state,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                latency_ms=(time.monotonic() - job.started) * 1000,
                ttft_ms=ttft,
                cached=cached,
                error_code=error_code,
            )
            try:
                await self.coordinator.settle(reservation, actual_tokens)
            except GatewayError:
                self.settlement_failures += 1
            self.metrics.observe(
                job.tenant,
                state,
                cached,
                usage.output_tokens,
                time.monotonic() - job.started,
                ttft / 1000 if ttft is not None else None,
            )
            job.phase = state
            self.jobs.pop((job.tenant, request.request_id), None)
            job.queue.put_nowait(None)

    async def close(self):
        await self.admission.drain()
        tasks = [job.task for job in self.jobs.values()]
        for job in list(self.jobs.values()):
            job.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await self.coordinator.close()
