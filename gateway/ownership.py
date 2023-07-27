"""Single gateway process owns a ledger; Redis does not make model workers shared."""
import fcntl
from pathlib import Path


class ProcessLock:
    def __init__(self, database: str | Path):
        self.database = Path(database).resolve()
        self.handle = None

    @property
    def held(self) -> bool:
        return self.handle is not None

    def __enter__(self):
        if self.held:
            raise RuntimeError("ownership already acquired")
        handle = self.database.with_suffix(".lock").open("a")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            handle.close()
            raise RuntimeError(
                "Another gateway process owns this ledger; use one worker."
            ) from error
        self.handle = handle
        return self

    def __exit__(self, *_):
        if self.handle is not None:
            fcntl.flock(self.handle, fcntl.LOCK_UN)
            self.handle.close()
            self.handle = None
