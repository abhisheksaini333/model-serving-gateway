import concurrent.futures
import pytest
from gateway.store import Store
from gateway.errors import GatewayError


def test_identity_is_durable_and_scoped_without_prompt_storage(tmp_path):
    path = tmp_path / "ledger.sqlite"
    first = Store(path)
    assert first.create("alpha", "one", "hash-a")["state"] == "queued"
    first.close()
    second = Store(path)
    with pytest.raises(GatewayError) as caught:
        second.create("alpha", "one", "hash-a")
    assert caught.value.code == "duplicate_request"
    with pytest.raises(GatewayError) as caught:
        second.create("alpha", "one", "hash-b")
    assert caught.value.code == "identity_conflict"
    assert second.create("beta", "one", "hash-a")["tenant"] == "beta"
    assert "prompt" not in second.get("alpha", "one")
    assert second.get("missing", "one") is None
    second.close()


def test_two_connections_cannot_admit_the_same_request_identity(tmp_path):
    path = tmp_path / "ledger.sqlite"
    stores = [Store(path), Store(path)]

    def submit(store):
        try:
            store.create("alpha", "same", "hash")
            return "accepted"
        except GatewayError as error:
            return error.code

    with concurrent.futures.ThreadPoolExecutor(2) as executor:
        outcomes = list(executor.map(submit, stores))
    assert sorted(outcomes) == ["accepted", "duplicate_request"]
    for store in stores:
        store.close()
