"""Bounded FIFO admission; a lease is released only after its worker stops."""
import asyncio
from collections import deque
from .errors import GatewayError


class Lease:
    def __init__(self, admission):
        self.admission = admission
        self.released = False

    async def release(self):
        async with self.admission.condition:
            if not self.released:
                self.released = True
                self.admission.active -= 1
                self.admission.condition.notify_all()


class Admission:
    def __init__(self, capacity: int, max_queue: int):
        if capacity < 1 or max_queue < 0:
            raise ValueError("positive capacity and nonnegative queue required")
        self.capacity = capacity
        self.max_queue = max_queue
        self.condition = asyncio.Condition()
        self.waiters = deque()
        self.active = 0
        self.draining = False

    def snapshot(self) -> dict:
        return dict(
            active=self.active,
            queued=len(self.waiters),
            capacity=self.capacity,
            max_queue=self.max_queue,
            draining=self.draining,
        )

    async def acquire(self, tenant: str, deadline: float) -> Lease:
        waiter = object()
        loop = asyncio.get_running_loop()
        async with self.condition:
            if self.draining:
                raise GatewayError("draining", "The gateway is draining.")
            if deadline <= loop.time():
                raise GatewayError(
                    "deadline_exceeded", "Request deadline expired.", 504
                )
            if self.active < self.capacity and not self.waiters:
                self.active += 1
                return Lease(self)
            if len(self.waiters) >= self.max_queue:
                raise GatewayError("queue_full", "The inference queue is full.", 503)
            self.waiters.append(waiter)
            try:
                while True:
                    if self.draining:
                        raise GatewayError("draining", "The gateway is draining.")
                    remaining = deadline - loop.time()
                    if remaining <= 0:
                        raise GatewayError(
                            "deadline_exceeded", "Request deadline expired.", 504
                        )
                    if self.waiters[0] is waiter and self.active < self.capacity:
                        self.waiters.popleft()
                        self.active += 1
                        self.condition.notify_all()
                        return Lease(self)
                    try:
                        await asyncio.wait_for(self.condition.wait(), remaining)
                    except asyncio.TimeoutError as error:
                        raise GatewayError(
                            "deadline_exceeded", "Request deadline expired.", 504
                        ) from error
            finally:
                if waiter in self.waiters:
                    self.waiters.remove(waiter)
                    self.condition.notify_all()

    async def drain(self):
        async with self.condition:
            self.draining = True
            self.condition.notify_all()
