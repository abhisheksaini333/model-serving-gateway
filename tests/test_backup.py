import sqlite3
import pytest
from gateway.backup import backup_ledger
from gateway.store import Store


def test_live_wal_backup_preserves_requests_and_audit_without_overwriting(tmp_path):
    source = tmp_path / "live.sqlite"
    store = Store(source)
    store.create("alpha", "one", "fingerprint")
    store.audit("backend_mode", "cpu-a", "draining")
    destination = tmp_path / "backup.sqlite"
    result = backup_ledger(source, destination)
    assert result["integrity"] == "ok" and result["requests"] == 1
    store.create("alpha", "two", "different")
    with sqlite3.connect(destination) as restored:
        assert restored.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 1
        assert (
            restored.execute("SELECT value FROM operator_audit").fetchone()[0]
            == "draining"
        )
    original = destination.read_bytes()
    with pytest.raises(FileExistsError):
        backup_ledger(source, destination)
    assert destination.read_bytes() == original
    with pytest.raises(ValueError):
        backup_ledger(source, source)
    store.close()
