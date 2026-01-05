"""Transparent nearest-rank workload summaries, including unsuccessful requests."""
import math


def distribution(values):
    if not values:
        return {"p50": None, "p95": None}
    ordered = sorted(values)
    return {
        name: ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]
        for name, fraction in [("p50", 0.5), ("p95", 0.95)]
    }


def summarize(rows):
    for row in rows:
        if type(row.get("status")) is not int or not 100 <= row["status"] <= 599:
            raise ValueError("HTTP status must be an integer between 100 and 599")
        if type(row.get("output_tokens")) is not int or row["output_tokens"] < 0:
            raise ValueError("Token counts must be nonnegative integers")
        for key in ("latency_ms", "ttft_ms"):
            value = row.get(key)
            if key == "ttft_ms" and value is None:
                continue
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError("Durations must be finite nonnegative numbers")
    successful = [row for row in rows if row["status"] == 200]
    seconds = sum(row["latency_ms"] for row in successful) / 1000
    return {
        "requests": len(rows),
        "error_rate": (len(rows) - len(successful)) / len(rows) if rows else 0,
        "latency_ms": distribution([row["latency_ms"] for row in rows]),
        "ttft_ms": distribution(
            [row["ttft_ms"] for row in successful if row["ttft_ms"] is not None]
        ),
        "successful_request_tokens_per_second": sum(
            row["output_tokens"] for row in successful
        )
        / seconds
        if seconds
        else 0,
    }
