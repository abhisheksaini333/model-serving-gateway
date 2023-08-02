import hashlib
import json
import pytest
from gateway.artifacts import verify_artifacts


def test_artifact_verification_rejects_modified_model_before_loading(tmp_path):
    (tmp_path / "weights.bin").write_bytes(b"original")
    manifest = [
        {
            "file": "weights.bin",
            "bytes": 8,
            "sha256": hashlib.sha256(b"original").hexdigest(),
        }
    ]
    assert verify_artifacts(tmp_path, manifest) == ["weights.bin"]
    (tmp_path / "weights.bin").write_bytes(b"modified")
    with pytest.raises(ValueError, match="hash"):
        verify_artifacts(tmp_path, manifest)


def test_manifest_cannot_escape_model_directory(tmp_path):
    with pytest.raises(ValueError):
        verify_artifacts(tmp_path, [{"file": "../outside", "bytes": 0, "sha256": ""}])
