"""Exercise an actual configured HTTP model, including overload and disconnects."""
import argparse
import asyncio
import json
import os
import platform
import subprocess
import time
import uuid
from pathlib import Path
import httpx
from gateway.benchmark import summarize

PROMPT = (
    "Translate English to German: The little girl walks along the river every morning "
    "with her grandfather. They watch the birds and talk about the flowers in the garden. "
    "When the weather is cold, they wear warm coats and carry a basket of fresh bread."
)


class Workload:
    def __init__(self, client, tenants, operator):
        self.client = client
        self.tenants = tenants
        self.operator = {"Authorization": "Bearer " + operator}

    def headers(self, tenant="alpha"):
        return {"Authorization": "Bearer " + self.tenants[tenant]["api_key"]}

    async def request(self, tenant="alpha", **options):
        payload = dict(
            model="flan-small",
            prompt=PROMPT,
            max_new_tokens=128,
            request_id=uuid.uuid4().hex,
            timeout_ms=10000,
        )
        payload.update(options)
        started = time.perf_counter()
        response = await self.client.post(
            "/v1/generate", json=payload, headers=self.headers(tenant)
        )
        body = response.json()
        return dict(
            status=response.status_code,
            request_id=payload["request_id"],
            latency_ms=(time.perf_counter() - started) * 1000,
            ttft_ms=body.get("ttft_ms"),
            output_tokens=body.get("usage", {}).get("output_tokens", 0),
            body=body,
        )

    async def summary(self):
        response = await self.client.get("/ops/summary", headers=self.operator)
        response.raise_for_status()
        return response.json()

    async def wait_idle(self):
        for _ in range(250):
            state = await self.summary()
            if state["admission"]["active"] == 0 and state["workers"] == 0:
                return state
            await asyncio.sleep(0.02)
        raise AssertionError(
            "Actual worker capacity did not return within five seconds"
        )

    async def cancel_stream(self, explicit=False):
        identity = uuid.uuid4().hex
        started = time.perf_counter()
        observed = None
        async with self.client.stream(
            "POST",
            "/v1/stream",
            headers=self.headers(),
            json={
                "model": "flan-small",
                "prompt": PROMPT,
                "request_id": identity,
                "max_new_tokens": 128,
                "timeout_ms": 10000,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    event = json.loads(line[6:])
                    if event["type"] == "token":
                        observed = await self.summary()
                        if explicit:
                            cancelled = await self.client.post(
                                "/v1/requests/" + identity + "/cancel",
                                headers=self.headers(),
                            )
                            cancelled.raise_for_status()
                        break
        idle = await self.wait_idle()
        status = await self.client.get(
            "/v1/requests/" + identity, headers=self.headers()
        )
        record = status.json()
        assert (
            observed["workers"] == 1
        ), "Cancellation must occur during real generation"
        assert record["state"] == "cancelled", record
        assert record["output_tokens"] > 0
        return dict(
            mode="explicit" if explicit else "client_disconnect",
            observed_worker_count=observed["workers"],
            final_worker_count=idle["workers"],
            capacity_after=idle["admission"],
            record=record,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )


async def run(args):
    tenants = json.loads(os.environ["GATEWAY_TENANTS_JSON"])
    operator = os.environ["GATEWAY_OPERATOR_KEY"]
    async with httpx.AsyncClient(
        base_url=args.base_url, timeout=30, trust_env=False
    ) as client:
        work = Workload(client, tenants, operator)
        initial = await work.summary()
        assert (
            initial["admission"]["max_queue"] == 2
        ), "Use queue size2 for this workload"
        normal = [await work.request() for _ in range(8)]
        assert all(row["status"] == 200 for row in normal)
        overloaded = await asyncio.gather(*[work.request() for _ in range(12)])
        assert any(
            row["body"].get("error", {}).get("code") == "queue_full"
            for row in overloaded
        )
        await work.wait_idle()
        cancellation = [
            await work.cancel_stream(),
            await work.cancel_stream(explicit=True),
        ]
        deadline = await work.request(timeout_ms=100)
        assert deadline["status"] == 504, deadline
        limited = [await work.request("limited") for _ in range(3)]
        assert [row["status"] for row in limited] == [200, 200, 429], limited
        disabled = await client.post(
            "/ops/backends/cpu-a/mode",
            headers=work.operator,
            json={"mode": "disabled", "expected_mode": "enabled"},
        )
        disabled.raise_for_status()
        try:
            outage = await work.request()
            assert outage["status"] == 503
        finally:
            restored = await client.post(
                "/ops/backends/cpu-a/mode",
                headers=work.operator,
                json={"mode": "enabled", "expected_mode": "disabled"},
            )
            restored.raise_for_status()
        recovery = await work.request()
        assert recovery["status"] == 200
        redis_outage = None
        if args.redis_container:
            if not args.redis_container.startswith("serving-gateway-"):
                raise ValueError(
                    "Outage probe accepts only a serving-gateway- prefixed container"
                )
            subprocess.run(
                ["docker", "stop", args.redis_container],
                check=True,
                capture_output=True,
            )
            try:
                redis_outage = await work.request()
                assert redis_outage["status"] == 503
                assert (
                    redis_outage["body"]["error"]["code"] == "coordination_unavailable"
                )
            finally:
                subprocess.run(
                    ["docker", "start", args.redis_container],
                    check=True,
                    capture_output=True,
                )
            for _ in range(100):
                ready = await client.get("/health/ready")
                if ready.status_code == 200:
                    break
                await asyncio.sleep(0.1)
            assert ready.status_code == 200
        final = await work.wait_idle()
    report = {
        "adapter": "actual-transformers-cpu-over-http",
        "model": "google/flan-t5-small",
        "revision": initial["backends"][0]["revision"],
        "hardware": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "logical_cpus": os.cpu_count(),
            "torch_threads": 2,
        },
        "workload": {
            "prompt": PROMPT,
            "max_new_tokens": 128,
            "normal_requests": 8,
            "overload_concurrency": 12,
            "capacity": 1,
            "queue_size": 2,
            "cache_enabled": False,
        },
        "normal": {"summary": summarize(normal), "requests": normal},
        "overload": {"summary": summarize(overloaded), "requests": overloaded},
        "cancellation": cancellation,
        "deadline": deadline,
        "quota": limited,
        "backend_outage": {
            "method": "operator disables the real backend before admission",
            "request": outage,
            "recovery": recovery,
        },
        "redis_outage": redis_outage,
        "final": final,
        "limits": [
            "CPU only; no GPU or vLLM measurement",
            "Small local workload, shared host; not a capacity SLA",
            "TTFT means first nonempty decoded text, not first internal decoder token",
            "Tokens per second includes successful request queue and inference latency",
        ],
    }
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "normal": report["normal"]["summary"],
                "overload": report["overload"]["summary"],
                "cancelled_workers": [
                    row["final_worker_count"] for row in cancellation
                ],
                "deadline": deadline["status"],
                "quota": [row["status"] for row in limited],
                "backend_outage": outage["status"],
                "redis_outage": redis_outage["status"] if redis_outage else None,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8093")
    parser.add_argument("--output", default="evidence/http-benchmark.json")
    parser.add_argument(
        "--redis-container",
        help="Explicitly stop/start only this dedicated test container",
    )
    asyncio.run(run(parser.parse_args()))
