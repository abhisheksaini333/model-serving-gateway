import pytest
from pydantic import ValidationError
from gateway.contracts import GenerationRequest


def test_normalized_defaults_are_bounded():
    request = GenerationRequest(model="flan-small", prompt="Summarize this.")
    assert request.max_new_tokens == 64
    assert request.timeout_ms == 30000
    assert request.temperature == 0
    assert request.request_id


@pytest.mark.parametrize(
    "field,value",
    [
        ("prompt", " "),
        ("prompt", "x" * 16385),
        ("model", "../private"),
        ("request_id", "bad\nidentity"),
        ("max_new_tokens", 0),
        ("max_new_tokens", 513),
        ("timeout_ms", 99),
        ("temperature", float("nan")),
    ],
)
def test_rejects_unbounded_or_ambiguous_input(field, value):
    payload = dict(model="flan-small", prompt="hello")
    payload[field] = value
    with pytest.raises(ValidationError):
        GenerationRequest(**payload)


def test_unknown_options_are_not_silently_ignored():
    with pytest.raises(ValidationError):
        GenerationRequest(model="flan-small", prompt="hello", tenant="other")
