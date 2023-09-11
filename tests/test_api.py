import os
import uuid
import pytest
from fastapi.testclient import TestClient
from gateway.api import create_app
from gateway.auth import Authenticator
from gateway.admission import Admission
from gateway.coordination import RedisCoordinator, TenantLimits
from gateway.engine import Engine
from gateway.routing import Router
from gateway.store import Store
from test_engine import CountingBackend
from test_auth import ALPHA, BETA, OPERATOR

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_REDIS_URL"), reason="Requires dedicated Redis"
)


def make_client(tmp_path):
    coordinator = RedisCoordinator(
        os.environ["TEST_REDIS_URL"], "api-" + uuid.uuid4().hex
    )
    engine = Engine(
        Router([CountingBackend()]),
        Admission(1, 2),
        coordinator,
        Store(tmp_path / "ledger.sqlite"),
    )
    auth = Authenticator(
        {"alpha": (ALPHA, TenantLimits()), "beta": (BETA, TenantLimits())}, OPERATOR
    )
    return TestClient(create_app(engine, auth))


def test_authenticated_json_contract_and_safe_errors(tmp_path):
    with make_client(tmp_path) as client:
        payload = {"model": "flan-small", "prompt": "hello", "request_id": "one"}
        assert client.post("/v1/generate", json=payload).status_code == 401
        response = client.post(
            "/v1/generate", json=payload, headers={"Authorization": "Bearer " + ALPHA}
        )
        assert response.status_code == 200
        assert response.json()["text"] == "answer"
        assert response.json()["usage"]["output_tokens"] == 1
        duplicate = client.post(
            "/v1/generate", json=payload, headers={"Authorization": "Bearer " + ALPHA}
        )
        assert duplicate.status_code == 409
        assert client.get("/health/live").status_code == 200


def test_sse_normalized_token_and_terminal_events(tmp_path):
    with make_client(tmp_path) as client:
        response = client.post(
            "/v1/stream",
            json={"model": "flan-small", "prompt": "hello"},
            headers={"Authorization": "Bearer " + ALPHA},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: token" in response.text
        assert "event: result" in response.text
        assert '"text":"answer"' in response.text
        assert response.headers["cache-control"] == "no-store"


def test_reading_request_status_never_crosses_tenant(tmp_path):
    with make_client(tmp_path) as client:
        headers = {"Authorization": "Bearer " + ALPHA}
        client.post(
            "/v1/generate",
            json={"model": "flan-small", "prompt": "hello", "request_id": "private"},
            headers=headers,
        )
        own = client.get("/v1/requests/private", headers=headers)
        other = client.get(
            "/v1/requests/private", headers={"Authorization": "Bearer " + BETA}
        )
        assert own.json()["state"] == "completed"
        assert "prompt" not in own.json()
        assert other.status_code == 404
