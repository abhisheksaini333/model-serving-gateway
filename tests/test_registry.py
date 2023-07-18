import pytest
from gateway.registry import BackendSpec, Registry
from gateway.errors import GatewayError


def backend(name="cpu-a", **kwargs):
    return BackendSpec(name=name, model="flan-small", revision="original", **kwargs)


def test_registry_preserves_priority_and_rejects_unknown_models():
    registry = Registry([backend("cpu-a"), backend("cpu-b")])
    assert [item.name for item in registry.for_model("flan-small")] == [
        "cpu-a",
        "cpu-b",
    ]
    with pytest.raises(GatewayError) as caught:
        registry.for_model("absent")
    assert caught.value.code == "unknown_model"
    assert caught.value.status == 404


def test_duplicate_backends_and_ambiguous_model_revisions_are_rejected():
    with pytest.raises(ValueError):
        Registry([backend(), backend()])
    with pytest.raises(ValueError):
        Registry(
            [
                backend(),
                BackendSpec(name="cpu-b", model="flan-small", revision="different"),
            ]
        )


@pytest.mark.parametrize(
    "options", [{"capacity": 0}, {"max_input_tokens": 0}, {"name": "../x"}]
)
def test_invalid_backend_capacity_or_identifier_fails_startup(options):
    values = dict(name="cpu-a", model="flan-small", revision="original")
    values.update(options)
    with pytest.raises(ValueError):
        BackendSpec(**values)
