"""Create private demo credentials without overwriting an existing environment."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shlex


def create_environment(destination: Path, model_directory: Path):
    if not model_directory.is_dir():
        raise ValueError("download the verified model first")
    tenants = {
        name: {
            "api_key": secrets.token_urlsafe(32),
            "limits": {"requests": 500, "concurrent": 16, "output_tokens": 50000},
        }
        for name in ("alpha", "beta")
    }
    tenants["limited"] = {
        "api_key": secrets.token_urlsafe(32),
        "limits": {
            "requests": 2,
            "concurrent": 1,
            "output_tokens": 1024,
            "window_seconds": 60,
        },
    }
    values = {
        "MODEL_DIRECTORY": str(model_directory.resolve()),
        "GATEWAY_MODEL_PATH": str(model_directory.resolve()),
        "GATEWAY_TENANTS_JSON": json.dumps(tenants, separators=(",", ":")),
        "GATEWAY_OPERATOR_KEY": secrets.token_urlsafe(32),
        "GATEWAY_QUEUE_SIZE": "2",
        "GATEWAY_CACHE_TTL": "0",
        "GATEWAY_NAMESPACE": "gateway-" + secrets.token_hex(8),
        "GATEWAY_REDIS_URL": "redis://127.0.0.1:56383/0",
        "GATEWAY_DATABASE": "var/gateway.sqlite",
    }
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        for key, value in values.items():
            output.write(key + "=" + shlex.quote(value) + "\n")
        output.flush()
        os.fsync(output.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(".env"))
    args = parser.parse_args()
    create_environment(args.output, args.model_directory)
    print("Private environment created: " + str(args.output))


if __name__ == "__main__":
    main()
