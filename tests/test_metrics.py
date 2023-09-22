from gateway.admission import Admission
from gateway.metrics import Metrics


def test_metrics_measure_real_units_without_request_or_prompt_labels():
    metrics = Metrics(Admission(1, 4))
    metrics.observe("alpha", "completed", False, 3, 0.25, 0.05)
    metrics.observe("alpha", "completed", True, 0, 0.001, None)
    text = metrics.render().decode()
    assert 'gateway_output_tokens_total{tenant="alpha"} 3.0' in text
    assert 'gateway_latency_seconds_count{state="completed"} 2.0' in text
    assert "gateway_ttft_seconds_count 1.0" in text
    assert "gateway_queue_depth 0.0" in text
    assert "request_id" not in text and "prompt" not in text
