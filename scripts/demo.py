"""Stream a real request using the private demo tenant configuration."""
import argparse
import json
import os
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8093")
    args = parser.parse_args()
    key = json.loads(os.environ["GATEWAY_TENANTS_JSON"])["alpha"]["api_key"]
    request = Request(
        args.base_url.rstrip("/") + "/v1/stream",
        data=json.dumps(
            {
                "model": "flan-small",
                "prompt": "Translate English to German: The house is wonderful.",
                "max_new_tokens": 64,
            }
        ).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    with urlopen(request, timeout=35) as response:
        for line in response:
            if line.startswith(b"data:"):
                print(json.dumps(json.loads(line[5:]), indent=2))


if __name__ == "__main__":
    main()
