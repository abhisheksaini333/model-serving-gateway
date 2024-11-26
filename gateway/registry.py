"""Ordered backend configuration with an unambiguous public model revision."""
import re
from dataclasses import dataclass
from .errors import GatewayError


@dataclass(frozen=True)
class BackendSpec:
    name: str
    model: str
    revision: str
    capacity: int = 1
    max_input_tokens: int = 512
    max_output_tokens: int = 512

    def __post_init__(self):
        for identifier in (self.name, self.model):
            if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", identifier):
                raise ValueError("invalid backend or model identifier")
        if (
            not isinstance(self.revision, str) or not self.revision.strip()
            or any(type(v) is not int or v < 1 for v in (self.capacity, self.max_input_tokens, self.max_output_tokens))
        ):
            raise ValueError("revision and positive backend limits are required")


class Registry:
    def __init__(self, backends: list[BackendSpec]):
        self.backends = tuple(backends)
        names = [backend.name for backend in backends]
        if not names or len(names) != len(set(names)):
            raise ValueError("unique backends are required")
        revisions: dict[str, str] = {}
        for backend in backends:
            if (
                revisions.setdefault(backend.model, backend.revision)
                != backend.revision
            ):
                raise ValueError("fallback backends must share a model revision")

    def for_model(self, model: str) -> tuple[BackendSpec, ...]:
        candidates = tuple(
            backend for backend in self.backends if backend.model == model
        )
        if not candidates:
            raise GatewayError(
                "unknown_model", "The requested model is not registered.", 404
            )
        return candidates
