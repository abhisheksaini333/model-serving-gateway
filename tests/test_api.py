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


def make_client(tmp_path, static_dir=None):
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
    return TestClient(create_app(engine, auth, static_dir=static_dir))


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


def test_operator_controls_require_role_and_reject_stale_updates(tmp_path):
    with make_client(tmp_path) as client:
        operator = {"Authorization": "Bearer " + OPERATOR}
        tenant = {"Authorization": "Bearer " + ALPHA}
        assert client.get("/ops/summary", headers=tenant).status_code == 401
        summary = client.get("/ops/summary", headers=operator).json()
        assert summary["admission"]["capacity"] == 1
        changed = client.post(
            "/ops/backends/cpu-a/mode",
            headers=operator,
            json={"mode": "disabled", "expected_mode": "enabled"},
        )
        assert changed.status_code == 200
        stale = client.post(
            "/ops/backends/cpu-a/mode",
            headers=operator,
            json={"mode": "enabled", "expected_mode": "enabled"},
        )
        assert stale.status_code == 409
        assert client.get("/health/ready").status_code == 503
        assert (
            client.get("/ops/audit", headers=operator).json()[0]["value"] == "disabled"
        )
        assert client.get("/metrics", headers=operator).status_code == 200
        assert client.get("/metrics", headers=tenant).status_code == 401


def test_global_drain_refuses_cached_and_uncached_new_admission(tmp_path):
    with make_client(tmp_path) as client:
        tenant = {"Authorization": "Bearer " + ALPHA}
        payload = {"model": "flan-small", "prompt": "hello"}
        assert (
            client.post("/v1/generate", json=payload, headers=tenant).status_code == 200
        )
        assert (
            client.post(
                "/ops/drain", headers={"Authorization": "Bearer " + OPERATOR}
            ).status_code
            == 200
        )
        response = client.post("/v1/generate", json=payload, headers=tenant)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "draining"


def test_ledger_failure_returns_terminal_error_and_fails_readiness(tmp_path):
    with make_client(tmp_path) as client:

        def failed_finish(*args, **kwargs):
            raise OSError("private ledger path")

        client.app.state.engine.store.finish = failed_finish
        response = client.post(
            "/v1/generate",
            headers={"Authorization": "Bearer " + ALPHA},
            json={"model": "flan-small", "prompt": "hello"},
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "ledger_unavailable"
        assert "private" not in response.text
        assert client.get("/health/ready").status_code == 503


def test_transport_rejects_oversized_bodies_and_sets_browser_boundaries(tmp_path):
    with make_client(tmp_path) as client:
        response = client.post(
            "/v1/generate",
            content=b"x" * 131073,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 413
        headers = client.get("/health/live").headers
        assert headers["x-content-type-options"] == "nosniff"
        assert "frame-ancestors 'none'" in headers["content-security-policy"]


def test_compiled_console_is_served_without_shadowing_api(tmp_path):
    static = tmp_path / "console"
    static.mkdir()
    (static / "index.html").write_text("<h1>Operator console</h1>")
    with make_client(tmp_path, static_dir=static) as client:
        assert "Operator console" in client.get("/").text
        assert client.get("/health/live").json() == {"status": "live"}
        assert client.get("/%2e%2e/ledger.sqlite").status_code == 404


def test_operator_metadata_identifies_the_actual_serving_platform(tmp_path):
    import platform

    with make_client(tmp_path) as client:
        result = client.get(
            "/ops/summary", headers={"Authorization": "Bearer " + OPERATOR}
        ).json()
        assert result["runtime"]["architecture"] == platform.machine()
        assert result["runtime"]["python"] == platform.python_version()
