import pytest
from gateway.breaker import CircuitBreaker

@pytest.mark.parametrize("settings", [{"threshold":True},{"threshold":1.5},{"cooldown":float("nan")},{"cooldown":float("inf")},{"cooldown":True}])
def test_invalid_circuit_configuration(settings):
    with pytest.raises(ValueError): CircuitBreaker(**settings)
