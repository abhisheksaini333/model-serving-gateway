import json
import pytest
from gateway.settings import Settings
from test_auth import ALPHA, OPERATOR


def environment(tmp_path):
    return {
        "GATEWAY_MODEL_PATH": str(tmp_path),
        "GATEWAY_OPERATOR_KEY": OPERATOR,
        "GATEWAY_TENANTS_JSON": json.dumps({"alpha": {"api_key": ALPHA}}),
    }


def test_settings_are_bounded_and_do_not_print_secrets(tmp_path):
    settings = Settings.from_env(environment(tmp_path))
    assert settings.queue_size == 4
    assert settings.auth.authenticate("Bearer " + ALPHA).tenant == "alpha"
    assert ALPHA not in repr(settings) and OPERATOR not in repr(settings)


@pytest.mark.parametrize(
    "name,value",
    [
        ("GATEWAY_QUEUE_SIZE", "-1"),
        ("GATEWAY_QUEUE_SIZE", "1000000"),
        ("GATEWAY_CACHE_TTL", "9999"),
        ("GATEWAY_REDIS_URL", "file:///tmp/redis"),
    ],
)
def test_bad_environment_fails_before_startup(tmp_path, name, value):
    env = environment(tmp_path)
    env[name] = value
    with pytest.raises(ValueError):
        Settings.from_env(env)
