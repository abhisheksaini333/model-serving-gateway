"""Ordered capacity-aware routing; emitted output is an irreversible retry boundary."""
import threading
from dataclasses import dataclass
from .backends import GenerationEvent
from .breaker import CircuitBreaker
from .contracts import GenerationRequest
from .errors import GatewayError
from .registry import Registry


@dataclass(frozen=True)
class RoutedEvent:
    backend: str
    event: GenerationEvent


class Router:
    def __init__(self, backends: list, failure_threshold=3, cooldown=10):
        self.registry = Registry([backend.spec for backend in backends])
        self.backends = {backend.spec.name: backend for backend in backends}
        self.active = {name: 0 for name in self.backends}
        self.modes = {name: "enabled" for name in self.backends}
        self.breakers = {
            name: CircuitBreaker(failure_threshold, cooldown) for name in self.backends
        }

    def snapshot(self):
        return [
            dict(
                name=spec.name,
                model=spec.model,
                revision=spec.revision,
                active=self.active[spec.name],
                capacity=spec.capacity,
                mode=self.modes[spec.name],
                circuit=self.breakers[spec.name].state,
                recovery_available=self.breakers[spec.name].available,
                failures=self.breakers[spec.name].failures,
            )
            for spec in self.registry.backends
        ]

    def set_mode(self, name: str, mode: str):
        if name not in self.backends:
            raise GatewayError("unknown_backend", "Backend is not registered.", 404)
        if mode not in {"enabled", "draining", "disabled"}:
            raise GatewayError(
                "invalid_mode", "Choose enabled, draining or disabled.", 422
            )
        self.modes[name] = mode

    async def stream(self, request: GenerationRequest, cancel: threading.Event):
        last_error = GatewayError("unavailable", "No inference backend is available.")
        for spec in self.registry.for_model(request.model):
            if cancel.is_set():
                raise GatewayError("cancelled", "Request was cancelled.", 499)
            name = spec.name
            if self.modes[name] != "enabled" or self.active[name] >= spec.capacity:
                continue
            breaker = self.breakers[name]
            if not breaker.acquire():
                continue
            self.active[name] += 1
            emitted = False
            complete = False
            stream = self.backends[name].stream(request, cancel)
            try:
                async for event in stream:
                    if complete:
                        raise GatewayError("backend_failed", "Backend emitted data after completion.")
                    if event.usage is not None:
                        if event.finish_reason not in {"stop", "length", "cancelled"}:
                            raise GatewayError("backend_failed", "Backend completion is invalid.")
                        complete = True
                    if event.text or event.usage is not None:
                        emitted = True
                        yield RoutedEvent(name, event)
                if not complete:
                    raise GatewayError("backend_failed", "Backend stream ended without usage.")
                breaker.success()
                return
            except GatewayError as error:
                if error.code == "backend_failed":
                    breaker.failure()
                else:
                    breaker.abandon()
                if emitted or error.code != "backend_failed":
                    raise
                last_error = error
            except Exception:
                breaker.failure()
                last_error = GatewayError(
                    "backend_failed", "The inference backend failed."
                )
                if emitted:
                    raise last_error from None
            finally:
                try:
                    await stream.aclose()
                finally:
                    self.active[name] -= 1
                    breaker.abandon()
        raise last_error
