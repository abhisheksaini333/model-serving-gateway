import pytest
from gateway.auth import Authenticator
from gateway.coordination import TenantLimits

@pytest.mark.parametrize("character", [" ","\r","\n","\t"])
def test_unusable_http_credentials_rejected(character):
    with pytest.raises(ValueError): Authenticator({"tenant":("a"*24+character,TenantLimits())},"b"*24)
