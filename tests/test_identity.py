from gateway.contracts import GenerationRequest
from gateway.identity import fingerprint, cache_key


def test_identity_ignores_request_id_but_binds_all_generation_options():
    first = GenerationRequest(model="flan-small", prompt="hello", request_id="one")
    second = first.copy(update={"request_id": "two"})
    assert fingerprint(first) == fingerprint(second)
    assert fingerprint(first) != fingerprint(first.copy(update={"max_new_tokens": 10}))
    assert fingerprint(first) != fingerprint(first.copy(update={"timeout_ms": 500}))


def test_cache_is_scoped_to_tenant_model_revision_and_generation_options():
    request = GenerationRequest(model="flan-small", prompt="secret")
    key = cache_key("alpha", "revision-a", request)
    assert "secret" not in key
    assert key != cache_key("beta", "revision-a", request)
    assert key != cache_key("alpha", "revision-b", request)
    assert key == cache_key(
        "alpha", "revision-a", request.copy(update={"timeout_ms": 1000})
    )
    assert (
        cache_key("alpha", "revision-a", request.copy(update={"temperature": 0.5}))
        is None
    )
