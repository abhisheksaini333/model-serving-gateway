"""Download the pinned model to an external directory and verify every byte."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.request import urlopen
from .artifacts import verify_artifacts, validate_manifest


def download_model(directory, manifest, fetch=urlopen):
    validate_manifest(manifest)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for item in manifest:
        name = item["file"]
        if Path(name).name != name or not item["url"].startswith("https://"):
            raise ValueError("direct filename and HTTPS model artifact required")
        destination = directory / name
        if destination.exists() or destination.is_symlink():
            verify_artifacts(directory, [item])
            continue
        descriptor, temporary = tempfile.mkstemp(prefix=".download-", dir=directory)
        try:
            digest, size = hashlib.sha256(), 0
            with os.fdopen(descriptor, "wb") as output, fetch(
                item["url"], timeout=60
            ) as response:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    size += len(block)
                    if size > item["bytes"]:
                        raise ValueError("model artifact exceeds declared size")
                    digest.update(block)
                    output.write(block)
                output.flush()
                os.fsync(output.fileno())
            if size != item["bytes"] or digest.hexdigest() != item["sha256"]:
                raise ValueError("downloaded model artifact hash or size differs")
            # Hard-link installation is atomic and refuses to overwrite a racing file.
            os.chmod(temporary, 0o644)
            os.link(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return verify_artifacts(directory, manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    manifest = json.loads((Path(__file__).parent / "data/flan-small.json").read_text())
    files = download_model(args.directory, manifest)
    print(
        json.dumps(
            {"directory": str(args.directory.resolve()), "verified_files": files}
        )
    )


if __name__ == "__main__":
    main()
