"""Construct one gateway process from verified local resources."""
import json
from importlib.resources import files
from .admission import Admission
from .api import create_app
from .artifacts import verify_artifacts
from .backends import LocalTransformersBackend
from .coordination import RedisCoordinator
from .engine import Engine
from .ownership import ProcessLock
from .registry import BackendSpec
from .routing import Router
from .store import Store


def build_app(settings):
    settings.database.parent.mkdir(parents=True, exist_ok=True)
    owner = ProcessLock(settings.database)
    owner.__enter__()
    store = None
    try:
        manifest = json.loads(
            files("gateway").joinpath("data/flan-small.json").read_text()
        )
        verify_artifacts(settings.model_path, manifest)
        spec = BackendSpec("cpu-a", "flan-small", manifest[0]["revision"])
        backend = LocalTransformersBackend.load(spec, str(settings.model_path))
        store = Store(settings.database)
        store.recover(owner)
        coordinator = RedisCoordinator(settings.redis_url, settings.namespace)
        engine = Engine(
            Router([backend]),
            Admission(spec.capacity, settings.queue_size),
            coordinator,
            store,
            settings.cache_ttl,
        )
        return create_app(engine, settings.auth, owner=owner)
    except BaseException:
        if store is not None:
            store.close()
        owner.__exit__(None, None, None)
        raise
