"""Server-managed tenant identity and separate operator credentials."""
import hmac
import re
from dataclasses import dataclass
from .coordination import TenantLimits
from .errors import GatewayError


@dataclass(frozen=True)
class Principal:
    tenant: str
    limits: TenantLimits
    operator: bool = False


class Authenticator:
    def __init__(self, tenants: dict[str, tuple[str, TenantLimits]], operator_key: str):
        keys = [value[0] for value in tenants.values()] + [operator_key]
        if not tenants or len(keys) != len(set(keys)):
            raise ValueError("unique tenant and operator credentials required")
        if any(
            not isinstance(key, str) or not 24 <= len(key) <= 256 or not key.isascii() or any(ord(c) < 33 or ord(c) > 126 for c in key)
            for key in keys
        ):
            raise ValueError("credentials must contain 24 to 256 ASCII characters")
        if any(not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", tenant) for tenant in tenants):
            raise ValueError("invalid tenant identifier")
        self._tenants = tenants.copy()
        self._operator_key = operator_key

    def authenticate(self, authorization: str | None, *, operator=False) -> Principal:
        token = (
            authorization[7:]
            if authorization and authorization.startswith("Bearer ")
            else ""
        )
        if not token.isascii() or len(token) > 256:
            token = ""
        if operator:
            if hmac.compare_digest(token, self._operator_key):
                return Principal("operator", TenantLimits(), operator=True)
        else:
            matched = None
            for tenant, (key, limits) in self._tenants.items():
                if hmac.compare_digest(token, key):
                    matched = Principal(tenant, limits)
            if matched:
                return matched
        raise GatewayError(
            "unauthorized", "A valid bearer credential is required.", 401
        )
