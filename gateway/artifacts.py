"""Verify original model bytes before deserializing a checkpoint."""
import hashlib
import re
from urllib.parse import urlparse
from pathlib import Path


def validate_manifest(manifest):
    if not manifest:
        raise ValueError("model artifact manifest is empty")
    names = set()
    for item in manifest:
        name = item.get("file")
        if not isinstance(name, str) or not name or name in {".", ".."} or Path(name).name != name or "\\" in name or name in names:
            raise ValueError("unique direct artifact filenames required")
        names.add(name)
        if type(item.get("bytes")) is not int or item["bytes"] < 1 or not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ValueError("positive artifact size and SHA-256 digest required")
        if "url" in item:
            url = urlparse(item["url"])
            if url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment:
                raise ValueError("HTTPS artifact URL required")


def verify_artifacts(directory: str | Path, manifest: list[dict]) -> list[str]:
    validate_manifest(manifest)
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
