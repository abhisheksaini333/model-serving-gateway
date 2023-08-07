import asyncio
import pytest
from gateway.admission import Admission
from gateway.errors import GatewayError


def test_bounded_fifo_queue_and_idempotent_capacity_release():
    async def scenario():
        admission = Admission(capacity=1, max_queue=1)
        first = await admission.acquire("alpha", asyncio.get_running_loop().time() + 5)
        waiting = asyncio.create_task(
            admission.acquire("beta", asyncio.get_running_loop().time() + 5)
        )
        await asyncio.sleep(0)
        assert admission.snapshot() == {
            "active": 1,
            "queued": 1,
            "capacity": 1,
            "max_queue": 1,
            "draining": False,
        }
        with pytest.raises(GatewayError) as error:
            await admission.acquire("gamma", asyncio.get_running_loop().time() + 5)
        assert error.value.code == "queue_full"
        await first.release()
        second = await waiting
        await first.release()
        assert admission.snapshot()["active"] == 1
        await second.release()
        assert admission.snapshot()["active"] == 0

    asyncio.run(scenario())


def test_cancelled_and_expired_waiters_leave_no_queue_slots():
    async def scenario():
        admission = Admission(1, 2)
        lease = await admission.acquire("alpha", asyncio.get_running_loop().time() + 2)
        waiting = asyncio.create_task(
            admission.acquire("beta", asyncio.get_running_loop().time() + 2)
        )
        await asyncio.sleep(0)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        with pytest.raises(GatewayError) as error:
            await admission.acquire("beta", asyncio.get_running_loop().time() + 0.01)
        assert error.value.code == "deadline_exceeded"
        assert admission.snapshot()["queued"] == 0
        await lease.release()

    asyncio.run(scenario())


def test_draining_rejects_queued_and_new_work_but_retains_active_lease():
    async def scenario():
        admission = Admission(1, 2)
        lease = await admission.acquire("alpha", asyncio.get_running_loop().time() + 2)
        waiting = asyncio.create_task(
            admission.acquire("beta", asyncio.get_running_loop().time() + 2)
        )
        await asyncio.sleep(0)
        await admission.drain()
        with pytest.raises(GatewayError) as error:
            await waiting
        assert error.value.code == "draining"
        assert admission.snapshot()["active"] == 1
        await lease.release()

    asyncio.run(scenario())
