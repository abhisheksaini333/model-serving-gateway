import pytest
from gateway.ownership import ProcessLock
from gateway.store import Store


def test_restart_requires_exclusive_ownership_before_abandoning_inflight(tmp_path):
    path = tmp_path / "ledger.sqlite"
    store = Store(path)
    store.create("alpha", "queued", "hash")
    store.create("alpha", "running", "hash")
    store.start("alpha", "running", "cpu-a")
    store.create("alpha", "done", "hash")
    store.finish("alpha", "done", "completed", output_tokens=2)
    first = ProcessLock(path)
    with first:
        with pytest.raises(RuntimeError):
            with ProcessLock(path):
                pass
        assert store.recover(first) == 2
    with pytest.raises(RuntimeError):
        store.recover(first)
    assert store.get("alpha", "running")["state"] == "abandoned"
    assert store.get("alpha", "done")["output_tokens"] == 2
    with ProcessLock(path):
        pass
    store.close()
