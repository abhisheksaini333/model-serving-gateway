from gateway.benchmark import summarize


def test_workload_summary_preserves_errors_and_uses_seconds_for_throughput():
    rows = [
        dict(status=200, latency_ms=100, ttft_ms=20, output_tokens=10),
        dict(status=503, latency_ms=10, ttft_ms=None, output_tokens=0),
        dict(status=200, latency_ms=300, ttft_ms=60, output_tokens=20),
    ]
    result = summarize(rows)
    assert result["requests"] == 3
    assert result["error_rate"] == 1 / 3
    assert result["latency_ms"]["p50"] == 100
    assert result["latency_ms"]["p95"] == 300
    assert result["successful_request_tokens_per_second"] == 75
    assert result["ttft_ms"]["p50"] == 20
