"""Bounded-label Prometheus measurements; times are seconds, tokens are model IDs."""
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)


class Metrics:
    def __init__(self, admission):
        self.registry = CollectorRegistry()
        self.requests = Counter(
            "gateway_requests_total",
            "Terminal admitted requests",
            ["tenant", "state", "cached"],
            registry=self.registry,
        )
        self.tokens = Counter(
            "gateway_output_tokens_total",
            "Actually generated output tokens",
            ["tenant"],
            registry=self.registry,
        )
        self.latency = Histogram(
            "gateway_latency_seconds",
            "Admission to terminal latency",
            ["state"],
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 120),
            registry=self.registry,
        )
        self.ttft = Histogram(
            "gateway_ttft_seconds",
            "Admission to first nonempty generated text",
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 120),
            registry=self.registry,
        )
        Gauge(
            "gateway_queue_depth", "Waiting inference requests", registry=self.registry
        ).set_function(lambda: admission.snapshot()["queued"])
        Gauge(
            "gateway_active_requests", "Active capacity leases", registry=self.registry
        ).set_function(lambda: admission.active)

    def observe(self, tenant, state, cached, output_tokens, latency, ttft):
        self.requests.labels(tenant, state, str(cached).lower()).inc()
        self.tokens.labels(tenant).inc(output_tokens)
        self.latency.labels(state).observe(latency)
        if ttft is not None and not cached:
            self.ttft.observe(ttft)

    def render(self):
        return generate_latest(self.registry)
