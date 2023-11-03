"""Normalized JSON and SSE transport. No SSE bytes precede the first backend output."""
import asyncio
import json
from pathlib import Path
from contextlib import asynccontextmanager
import anyio
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse
from .contracts import GenerationRequest
from .errors import GatewayError
from .operations import operator_routes
from .transport import TransportBoundary


def event_error(event):
    error = event["error"]
    return GatewayError(error["code"], error["message"], event["status"])


def sse(event):
    return (
        "event: "
        + event["type"]
        + "\ndata: "
        + json.dumps(event, separators=(",", ":"))
        + "\n\n"
    )


async def watch_disconnect(request, job):
    while not job.task.done():
        if await request.is_disconnected():
            job.cancel()
            return
        await asyncio.sleep(0.02)


async def stop_watcher(task):
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


def create_app(engine, auth, owner=None, static_dir=None):
    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            await engine.close()
            engine.store.close()
            if owner is not None:
                owner.__exit__(None, None, None)

    app = FastAPI(title="Model Serving Gateway", version="0.1.0", lifespan=lifespan)
    app.add_middleware(TransportBoundary)
    app.state.engine = engine
    app.state.auth = auth

    @app.exception_handler(GatewayError)
    async def gateway_error(request, error):
        headers = {"Cache-Control": "no-store"}
        if error.status == 429:
            headers["Retry-After"] = "1"
        return JSONResponse(error.payload(), status_code=error.status, headers=headers)

    @app.get("/health/live")
    async def live():
        return {"status": "live"}

    @app.get("/health/ready")
    async def ready():
        engine.check_ready()
        await engine.coordinator.healthy()
        if engine.admission.draining:
            raise GatewayError("draining", "The gateway is draining.")
        if not any(
            item["mode"] == "enabled" and item["circuit"] != "open"
            for item in engine.router.snapshot()
        ):
            raise GatewayError("unavailable", "No inference backend is available.")
        return {"status": "ready"}

    @app.post("/v1/generate")
    async def generate(body: GenerationRequest, request: Request):
        principal = auth.authenticate(request.headers.get("authorization"))
        job = await engine.submit(principal.tenant, body, principal.limits)
        watcher = asyncio.create_task(watch_disconnect(request, job))
        result = None
        try:
            async for event in job.events():
                if event["type"] == "error":
                    raise event_error(event)
                if event["type"] == "result":
                    result = event["response"]
            if result is None:
                raise GatewayError("cancelled", "Request was cancelled.", 499)
            return JSONResponse(result, headers={"Cache-Control": "no-store"})
        finally:
            await stop_watcher(watcher)
            if not job.task.done():
                job.cancel()
                with anyio.CancelScope(shield=True):
                    await asyncio.shield(job.task)

    @app.post("/v1/stream")
    async def stream(body: GenerationRequest, request: Request):
        principal = auth.authenticate(request.headers.get("authorization"))
        job = await engine.submit(principal.tenant, body, principal.limits)
        watcher = asyncio.create_task(watch_disconnect(request, job))
        try:
            first = await job.queue.get()
            if first is None:
                raise GatewayError("cancelled", "Request was cancelled.", 499)
            if first["type"] == "error":
                await asyncio.shield(job.task)
                raise event_error(first)
        finally:
            await stop_watcher(watcher)

        async def body_events():
            try:
                yield sse(first)
                async for event in job.events():
                    yield sse(event)
            finally:
                if not job.task.done():
                    job.cancel()
                    with anyio.CancelScope(shield=True):
                        await asyncio.shield(job.task)

        return StreamingResponse(
            body_events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @app.get("/v1/requests/{request_id}")
    async def request_status(request_id: str, request: Request):
        principal = auth.authenticate(request.headers.get("authorization"))
        record = engine.store.get(principal.tenant, request_id)
        if record is None:
            raise GatewayError("not_found", "Request was not found.", 404)
        return record

    @app.post("/v1/requests/{request_id}/cancel")
    async def cancel_request(request_id: str, request: Request):
        principal = auth.authenticate(request.headers.get("authorization"))
        if not engine.cancel(principal.tenant, request_id):
            raise GatewayError("not_active", "No active request was found.", 404)
        return {"request_id": request_id, "cancellation_requested": True}

    app.include_router(operator_routes(engine, auth))
    if static_dir is None:
        packaged = Path(__file__).parent / "static"
        development = Path(__file__).parent.parent / "frontend" / "dist"
        static_dir = packaged if packaged.is_dir() else development
    if Path(static_dir).is_dir():
        app.mount(
            "/", StaticFiles(directory=str(static_dir), html=True), name="console"
        )
    return app
