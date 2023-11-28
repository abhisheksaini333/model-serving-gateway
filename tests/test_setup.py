import json
import shlex
import stat
import pytest
from gateway.setup import create_environment
from gateway.settings import Settings


def test_generated_environment_has_distinct_private_credentials_and_refuses_overwrite(
    tmp_path,
):
    model = tmp_path / "model files"
    model.mkdir()
    destination = tmp_path / ".env"
    create_environment(destination, model)
    values = dict(line.split("=", 1) for line in destination.read_text().splitlines())
    values = {key: shlex.split(value)[0] for key, value in values.items()}
    Settings.from_env(values)
    tenants = json.loads(values["GATEWAY_TENANTS_JSON"])
    keys = [entry["api_key"] for entry in tenants.values()] + [
        values["GATEWAY_OPERATOR_KEY"]
    ]
    assert len(set(keys)) == 4
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    original = destination.read_bytes()
    with pytest.raises(FileExistsError):
        create_environment(destination, model)
    assert destination.read_bytes() == original
