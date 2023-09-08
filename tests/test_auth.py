import pytest
from gateway.auth import Authenticator
from gateway.coordination import TenantLimits
from gateway.errors import GatewayError

ALPHA = "alpha-private-key-123456789"
BETA = "beta-private-key-1234567890"
OPERATOR = "operator-private-key-123456"


def test_credentials_bind_tenant_and_operator_roles():
    auth = Authenticator(
        {"alpha": (ALPHA, TenantLimits()), "beta": (BETA, TenantLimits())}, OPERATOR
    )
    assert auth.authenticate("Bearer " + ALPHA).tenant == "alpha"
    assert auth.authenticate("Bearer " + BETA).tenant == "beta"
    assert auth.authenticate("Bearer " + OPERATOR, operator=True).operator
    for token, operator in [(ALPHA, True), (OPERATOR, False), ("wrong", False)]:
        with pytest.raises(GatewayError) as caught:
            auth.authenticate("Bearer " + token, operator=operator)
        assert caught.value.status == 401
        assert token not in str(caught.value)


def test_duplicate_or_weak_credentials_fail_startup():
    with pytest.raises(ValueError):
        Authenticator(
            {"alpha": (ALPHA, TenantLimits()), "beta": (ALPHA, TenantLimits())},
            OPERATOR,
        )
    with pytest.raises(ValueError):
        Authenticator({"alpha": ("short", TenantLimits())}, OPERATOR)
    with pytest.raises(ValueError):
        Authenticator({"alpha": (ALPHA, TenantLimits())}, ALPHA)
