"""Create a consistent SQLite snapshot, including committed WAL records."""
import argparse
import json
import os
from pathlib import Path
import sqlite3


def backup_ledger(source: Path, destination: Path):
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve() or not source.is_file():
        raise ValueError("distinct existing source ledger required")
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    original = snapshot = None
    try:
        original = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
        snapshot = sqlite3.connect(destination)
        original.backup(snapshot, pages=128, sleep=0.05)
        integrity = snapshot.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError("backup integrity check failed")
        requests = snapshot.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
        snapshot.commit()
        return {
            "integrity": integrity,
            "requests": requests,
            "destination": str(destination),
        }
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    finally:
        if snapshot is not None:
            snapshot.close()
        if original is not None:
            original.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(json.dumps(backup_ledger(args.source, args.destination)))


if __name__ == "__main__":
    main()
