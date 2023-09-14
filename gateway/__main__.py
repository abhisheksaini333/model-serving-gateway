"""Run an independently configured local inference gateway."""
import argparse
import os
import sys
from .settings import Settings
from .server import build_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8093)
    args = parser.parse_args()
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    try:
        settings = Settings.from_env()
        app = build_app(settings)
    except (ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, workers=1, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
