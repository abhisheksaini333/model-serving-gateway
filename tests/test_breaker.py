from gateway.breaker import CircuitBreaker


def test_threshold_cooldown_single_probe_and_recovery():
    now = [10.0]
    breaker = CircuitBreaker(threshold=2, cooldown=5, clock=lambda: now[0])
    assert breaker.acquire()
    breaker.failure()
    assert breaker.acquire()
    breaker.failure()
    assert breaker.state == "open"
    assert not breaker.acquire()
    now[0] = 15
    assert breaker.acquire()
    assert breaker.state == "half_open"
    assert not breaker.acquire()
    breaker.success()
    assert breaker.state == "closed"
    assert breaker.acquire()


def test_aborted_probe_is_not_permanently_stuck():
    now = [1.0]
    breaker = CircuitBreaker(1, 1, clock=lambda: now[0])
    breaker.failure()
    now[0] = 2
    assert breaker.acquire()
    breaker.abandon()
    assert breaker.acquire()
