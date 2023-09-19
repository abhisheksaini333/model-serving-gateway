import pytest
from gateway.store import Store


def test_operator_usage_and_recent_requests_are_bounded_and_text_free(tmp_path):
    store = Store(tmp_path / "ledger.sqlite")
    for tenant, identity, tokens in [
        ("alpha", "one", 2),
        ("alpha", "two", 3),
        ("beta", "one", 8),
    ]:
        store.create(tenant, identity, "hash")
        store.finish(tenant, identity, "completed", output_tokens=tokens)
    assert len(store.recent(tenant="alpha", limit=1)) == 1
    assert store.usage()[0]["output_tokens"] == 5
    assert store.usage()[1]["output_tokens"] == 8
    with pytest.raises(ValueError):
        store.recent(limit=1000)
    assert all("prompt" not in row for row in store.recent())
    store.close()


def test_operator_audit_is_append_only_and_bound_to_action(tmp_path):
    store = Store(tmp_path / "ledger.sqlite")
    store.audit("backend_mode", "cpu-a", "draining")
    store.audit("backend_mode", "cpu-a", "enabled")
    assert [row["value"] for row in store.audit_events()] == ["enabled", "draining"]
    with pytest.raises(ValueError):
        store.audit("arbitrary_secret", "cpu-a", "secret")
    store.close()
