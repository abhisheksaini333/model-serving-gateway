"""Verify original model bytes before deserializing a checkpoint."""
import hashlib
from pathlib import Path


def verify_artifacts(directory: str | Path, manifest: list[dict]) -> list[str]:
    directory = Path(directory).resolve()
    verified = []
    for item in manifest:
        name = item["file"]
        path = directory / name
        if (
            Path(name).name != name
            or path.is_symlink()
            or path.resolve().parent != directory
        ):
            raise ValueError("model artifact must be a direct regular file")
        if not path.is_file() or path.stat().st_size != item["bytes"]:
            raise ValueError("model artifact missing or size differs: " + name)
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != item["sha256"]:
            raise ValueError("model artifact hash differs: " + name)
        verified.append(name)
    if not verified:
        raise ValueError("model artifact manifest is empty")
    return verified
