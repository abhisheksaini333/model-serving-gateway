import pytest
from gateway.settings import Settings
from test_settings import environment

@pytest.mark.parametrize("field,bad", [("GATEWAY_REDIS_URL","redis:///0"),("GATEWAY_REDIS_URL","redis://localhost:bad/0"),("GATEWAY_REDIS_URL","redis://localhost/0#fragment"),("GATEWAY_NAMESPACE","bad namespace")])
def test_redis_configuration_fails_before_startup(tmp_path,field,bad):
    env=environment(tmp_path);env[field]=bad
    with pytest.raises(ValueError): Settings.from_env(env)
