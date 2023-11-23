import hashlib
import io
import pytest
from gateway.download import download_model


def manifest():
    return [
        {
            "file": "weights.bin",
            "bytes": 5,
            "sha256": hashlib.sha256(b"model").hexdigest(),
            "url": "https://example.test/model",
        }
    ]


def test_download_verifies_bytes_and_reuses_complete_artifact(tmp_path):
    calls = []

    def fetch(url, timeout):
        calls.append(url)
        return io.BytesIO(b"model")

    assert download_model(tmp_path / "model", manifest(), fetch) == ["weights.bin"]
    assert download_model(tmp_path / "model", manifest(), fetch) == ["weights.bin"]
    assert len(calls) == 1


def test_corrupt_download_never_installs_and_existing_corruption_is_preserved(tmp_path):
    target = tmp_path / "model"
    with pytest.raises(ValueError):
        download_model(target, manifest(), lambda *a, **kw: io.BytesIO(b"wrong"))
    assert not list(target.iterdir())
    (target / "weights.bin").write_bytes(b"local")
    with pytest.raises(ValueError):
        download_model(target, manifest())
    assert (target / "weights.bin").read_bytes() == b"local"
