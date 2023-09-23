"""Operator routes expose controls and measurements without generation text."""
from typing import Literal
from fastapi import APIRouter, Request, Query
from fastapi.responses import Response
from pydantic import BaseModel
from .errors import GatewayError


class ModeChange(BaseModel):
    mode: Literal["enabled", "draining", "disabled"]
    expected_mode: Literal["enabled", "draining", "disabled"]

    class Config:
        extra = "forbid"


def operator_routes(engine, auth):
    routes = APIRouter()

    def authorize(request):
        return auth.authenticate(request.headers.get("authorization"), operator=True)

    @routes.get("/ops/summary")
    async def summary(request: Request):
        authorize(request)
        return {
            "admission": engine.admission.snapshot(),
            "backends": engine.router.snapshot(),
            "usage": engine.store.usage(),
            "settlement_failures": engine.settlement_failures,
            "workers": sum(
                getattr(backend, "active_workers", 0)
                for backend in engine.router.backends.values()
            ),
        }

    @routes.get("/ops/requests")
    async def requests(request: Request, limit: int = Query(50, ge=1, le=100)):
        authorize(request)
        return engine.store.recent(limit=limit)

    @routes.get("/ops/audit")
    async def audit(request: Request):
        authorize(request)
        return engine.store.audit_events()

    @routes.post("/ops/backends/{name}/mode")
    async def mode(name: str, change: ModeChange, request: Request):
        authorize(request)
        if name not in engine.router.modes:
            raise GatewayError("unknown_backend", "Backend is not registered.", 404)
        if engine.router.modes[name] != change.expected_mode:
            raise GatewayError(
                "stale_mode", "Backend mode changed. Refresh before retrying.", 409
            )
        engine.store.audit("backend_mode", name, change.mode)
        engine.router.set_mode(name, change.mode)
        return {"name": name, "mode": change.mode}

    @routes.post("/ops/drain")
    async def drain(request: Request):
        authorize(request)
        engine.store.audit("gateway_mode", "gateway", "draining")
        await engine.admission.drain()
        return engine.admission.snapshot()

    @routes.post("/ops/requests/{tenant}/{request_id}/cancel")
    async def cancel(tenant: str, request_id: str, request: Request):
        authorize(request)
        if not engine.cancel(tenant, request_id):
            raise GatewayError("not_active", "No active request was found.", 404)
        return {"cancellation_requested": True}

    @routes.get("/metrics")
    async def metrics(request: Request):
        authorize(request)
        return Response(engine.metrics.render(), media_type="text/plain; version=0.0.4")

    return routes
