import json
import pytest
from gateway.server import build_app
from gateway.settings import Settings
from gateway.ownership import ProcessLock
from test_auth import ALPHA, OPERATOR


def test_bad_checkpoint_startup_releases_exclusive_ledger_lock(tmp_path):
    settings = Settings.from_env(
        {
            "GATEWAY_MODEL_PATH": str(tmp_path),
            "GATEWAY_DATABASE": str(tmp_path / "ledger.sqlite"),
            "GATEWAY_OPERATOR_KEY": OPERATOR,
            "GATEWAY_TENANTS_JSON": json.dumps({"alpha": {"api_key": ALPHA}}),
        }
    )
    with pytest.raises(ValueError, match="artifact"):
        build_app(settings)
    with ProcessLock(settings.database):
        pass
