import pytest
from gateway.benchmark import summarize

@pytest.mark.parametrize("field,bad", [("latency_ms",float("nan")),("latency_ms",-1),("output_tokens",True),("output_tokens",1.5),("ttft_ms",float("inf"))])
def test_benchmark_corruption_rejected(field,bad):
    row={"status":200,"latency_ms":10,"ttft_ms":1,"output_tokens":2};row[field]=bad
    with pytest.raises(ValueError): summarize([row])
