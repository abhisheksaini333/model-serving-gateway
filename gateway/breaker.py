"""A circuit grants one recovery probe after its cooldown."""
import time
import math


class CircuitBreaker:
    def __init__(self, threshold=3, cooldown=10, *, clock=time.monotonic):
        if type(threshold) is not int or threshold < 1 or type(cooldown) not in (int, float) or not math.isfinite(cooldown) or cooldown <= 0:
            raise ValueError("positive circuit threshold and cooldown required")
        self.threshold = threshold
        self.cooldown = cooldown
        self.clock = clock
        self.failures = 0
        self.opened_at = None
        self.probe = False

    @property
    def state(self):
        if self.probe:
            return "half_open"
        return "open" if self.opened_at is not None else "closed"

    @property
    def available(self):
        return self.opened_at is None or (
            not self.probe and self.clock() - self.opened_at >= self.cooldown
        )

    def acquire(self):
        if self.opened_at is None:
            return True
        if self.probe or self.clock() - self.opened_at < self.cooldown:
            return False
        self.probe = True
        return True

    def success(self):
        self.failures = 0
        self.opened_at = None
        self.probe = False

    def failure(self):
        self.failures += 1
        if self.probe or self.failures >= self.threshold:
            self.opened_at = self.clock()
        self.probe = False

    def abandon(self):
        self.probe = False
