"""SQLite request identities and usage; prompt and response text are not retained."""
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from .errors import GatewayError


class Store:
    def __init__(self, path: str | Path):
        self.connection = sqlite3.connect(
            str(path), timeout=5, check_same_thread=False, isolation_level=None
        )
        self.connection.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS requests (
                tenant TEXT NOT NULL,
                request_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                state TEXT NOT NULL,
                backend TEXT,
                created REAL NOT NULL,
                updated REAL NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                latency_ms REAL,
                ttft_ms REAL,
                cached INTEGER NOT NULL DEFAULT 0,
                error_code TEXT,
                PRIMARY KEY (tenant, request_id)
            )
        """
        )

    @contextmanager
    def transaction(self):
        with self.lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                yield self.connection
                self.connection.commit()
            except BaseException:
                self.connection.rollback()
                raise

    def create(self, tenant: str, request_id: str, fingerprint: str) -> dict:
        with self.transaction() as connection:
            existing = connection.execute(
                """
                SELECT fingerprint FROM requests WHERE tenant = ? AND request_id = ?
            """,
                (tenant, request_id),
            ).fetchone()
            if existing:
                if existing["fingerprint"] != fingerprint:
                    raise GatewayError(
                        "identity_conflict",
                        "Request ID was used for different options.",
                        409,
                    )
                raise GatewayError(
                    "duplicate_request", "Request ID has already been admitted.", 409
                )
            now = time.time()
            connection.execute(
                """
                INSERT INTO requests (tenant, request_id, fingerprint, state, created, updated)
                VALUES (?, ?, ?, 'queued', ?, ?)
            """,
                (tenant, request_id, fingerprint, now, now),
            )
        return self.get(tenant, request_id)

    def get(self, tenant: str, request_id: str) -> dict | None:
        with self.lock:
            row = self.connection.execute(
                """
                SELECT * FROM requests WHERE tenant = ? AND request_id = ?
            """,
                (tenant, request_id),
            ).fetchone()
            return dict(row) if row else None

    def close(self):
        with self.lock:
            self.connection.close()

    def start(self, tenant: str, request_id: str, backend: str) -> bool:
        with self.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE requests SET state = 'running', backend = ?, updated = ?
                WHERE tenant = ? AND request_id = ? AND state = 'queued'
            """,
                (backend, time.time(), tenant, request_id),
            )
            return cursor.rowcount == 1

    def finish(
        self,
        tenant: str,
        request_id: str,
        state: str,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: float | None = None,
        ttft_ms: float | None = None,
        cached: bool = False,
        error_code: str | None = None
    ) -> bool:
        if state not in {"completed", "failed", "cancelled", "expired", "abandoned"}:
            raise ValueError("terminal state required")
        if min(input_tokens, output_tokens) < 0:
            raise ValueError("token counts cannot be negative")
        with self.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE requests SET state = ?, updated = ?, input_tokens = ?,
                    output_tokens = ?, latency_ms = ?, ttft_ms = ?, cached = ?, error_code = ?
                WHERE tenant = ? AND request_id = ? AND state IN ('queued', 'running')
            """,
                (
                    state,
                    time.time(),
                    input_tokens,
                    output_tokens,
                    latency_ms,
                    ttft_ms,
                    int(cached),
                    error_code,
                    tenant,
                    request_id,
                ),
            )
            return cursor.rowcount == 1
