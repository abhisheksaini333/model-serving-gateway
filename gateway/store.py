"""SQLite request identities and usage; prompt and response text are not retained."""
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from .errors import GatewayError


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
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

        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS operator_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created REAL NOT NULL,
                action TEXT NOT NULL,
                target TEXT NOT NULL,
                value TEXT NOT NULL
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
        error_code: str | None = None,
        backend: str | None = None
    ) -> bool:
        if state not in {"completed", "failed", "cancelled", "expired", "abandoned"}:
            raise ValueError("terminal state required")
        if min(input_tokens, output_tokens) < 0:
            raise ValueError("token counts cannot be negative")
        with self.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE requests SET state = ?, updated = ?, input_tokens = ?,
                    output_tokens = ?, latency_ms = ?, ttft_ms = ?, cached = ?, error_code = ?, backend = COALESCE(?, backend)
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
                    backend,
                    tenant,
                    request_id,
                ),
            )
            return cursor.rowcount == 1

    def recover(self, owner) -> int:
        if not owner.held or owner.database != self.path:
            raise RuntimeError("exclusive ownership of this ledger is required")
        with self.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE requests SET state = 'abandoned', error_code = 'process_restart', updated = ?
                WHERE state IN ('queued', 'running')
            """,
                (time.time(),),
            )
            return cursor.rowcount

    def recent(self, *, tenant: str | None = None, limit: int = 50) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        where, values = ("WHERE tenant = ?", [tenant]) if tenant else ("", [])
        with self.lock:
            rows = self.connection.execute(
                "SELECT * FROM requests "
                + where
                + " ORDER BY created DESC, rowid DESC LIMIT ?",
                values + [limit],
            ).fetchall()
        return [dict(row) for row in rows]

    def usage(self) -> list[dict]:
        with self.lock:
            rows = self.connection.execute(
                """
                SELECT tenant, COUNT(*) AS requests, SUM(input_tokens) AS input_tokens,
                       SUM(output_tokens) AS output_tokens, SUM(cached) AS cache_hits,
                       SUM(CASE WHEN state = 'completed' THEN 1 ELSE 0 END) AS completed,
                       AVG(latency_ms) AS mean_latency_ms
                FROM requests GROUP BY tenant ORDER BY tenant
            """
            ).fetchall()
        return [dict(row) for row in rows]

    def audit(self, action: str, target: str, value: str):
        allowed = {
            "backend_mode": {"enabled", "draining", "disabled"},
            "gateway_mode": {"draining"},
        }
        if action not in allowed or value not in allowed[action] or len(target) > 80:
            raise ValueError("unsupported operator action")
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO operator_audit (created, action, target, value) VALUES (?, ?, ?, ?)
            """,
                (time.time(), action, target, value),
            )

    def audit_events(self) -> list[dict]:
        with self.lock:
            rows = self.connection.execute(
                "SELECT * FROM operator_audit ORDER BY id DESC LIMIT 100"
            ).fetchall()
        return [dict(row) for row in rows]
