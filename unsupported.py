#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import time

from pathlib import Path
from urllib.parse import urlsplit

from shortlinks import DATABASE_MAX_BYTES, DATABASE_PATH


RAW_RETENTION_SECONDS = int(
    os.environ.get("GOSTER_UNSUPPORTED_RETENTION_SECONDS", str(30 * 24 * 60 * 60))
)
MAX_PATH_LENGTH = 160
MAX_ROWS = int(os.environ.get("GOSTER_UNSUPPORTED_MAX_ROWS", "5000"))
TARGET_ROWS = int(os.environ.get("GOSTER_UNSUPPORTED_TARGET_ROWS", "4500"))
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,}$")


def safe_target(url: str) -> tuple[str, str, str]:
    """Return a deduplicated host/path target without query or fragment data."""
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        raise ValueError("unsupported target has no host")

    parts = []
    for raw_part in parsed.path.split("/"):
        if not raw_part:
            continue
        if (
            "@" in raw_part
            or raw_part.isdigit()
            or _UUID_RE.fullmatch(raw_part)
            or _TOKEN_RE.fullmatch(raw_part)
        ):
            parts.append(":redacted")
        else:
            parts.append(raw_part[:64])
    path_hint = "/" + "/".join(parts)
    path_hint = path_hint[:MAX_PATH_LENGTH] or "/"
    fingerprint = hashlib.sha256(f"{host}\0{path_hint}".encode()).hexdigest()
    return fingerprint, host, path_hint


class UnsupportedTargetStore:
    """Deduplicated adapter backlog without visitor or query-string data."""

    def __init__(
        self,
        path: str | Path = DATABASE_PATH,
        *,
        database_max_bytes: int = DATABASE_MAX_BYTES,
        max_rows: int = MAX_ROWS,
        target_rows: int = TARGET_ROWS,
    ) -> None:
        self.path = Path(path)
        self.database_max_bytes = database_max_bytes
        self.max_rows = max_rows
        self.target_rows = target_rows
        if self.database_max_bytes < 1024 * 1024:
            raise ValueError("database_max_bytes must be at least 1 MiB")
        if self.max_rows <= 0:
            raise ValueError("max_rows must be positive")
        if self.target_rows <= 0 or self.target_rows > self.max_rows:
            raise ValueError("target_rows must be positive and <= max_rows")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS unsupported_targets (
                    fingerprint TEXT PRIMARY KEY,
                    host TEXT NOT NULL,
                    path_hint TEXT NOT NULL,
                    first_seen_at INTEGER NOT NULL,
                    last_seen_at INTEGER NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS unsupported_targets_last_seen_idx "
                "ON unsupported_targets(last_seen_at)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
        max_pages = max(1, self.database_max_bytes // page_size)
        applied = int(
            connection.execute(f"PRAGMA max_page_count={max_pages}").fetchone()[0]
        )
        if applied * page_size > self.database_max_bytes:
            connection.close()
            raise RuntimeError("Database already exceeds configured byte cap.")
        return connection

    def _enforce_row_quota(self, db: sqlite3.Connection) -> None:
        rows = int(db.execute("SELECT COUNT(*) FROM unsupported_targets").fetchone()[0])
        if rows < self.max_rows:
            return
        trim_count = max(1, rows - self.target_rows + 1)
        db.execute(
            """
            DELETE FROM unsupported_targets
            WHERE fingerprint IN (
                SELECT fingerprint FROM unsupported_targets
                ORDER BY last_seen_at ASC
                LIMIT ?
            )
            """,
            (trim_count,),
        )

    def record(self, url: str, *, now: int | None = None) -> None:
        fingerprint, host, path_hint = safe_target(url)
        timestamp = int(time.time() if now is None else now)
        with self._connect() as db:
            self._enforce_row_quota(db)
            db.execute(
                """
                INSERT INTO unsupported_targets (
                    fingerprint, host, path_hint, first_seen_at, last_seen_at, attempts
                ) VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(fingerprint) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    attempts = unsupported_targets.attempts + 1
                """,
                (fingerprint, host, path_hint, timestamp, timestamp),
            )

    def list_targets(self, *, limit: int = 50) -> list[dict[str, object]]:
        if limit <= 0 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        with self._connect() as db:
            db.row_factory = sqlite3.Row
            return [
                dict(row)
                for row in db.execute(
                    """
                    SELECT host, path_hint, first_seen_at, last_seen_at, attempts
                    FROM unsupported_targets
                    ORDER BY attempts DESC, last_seen_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            ]

    def purge(
        self,
        *,
        now: int | None = None,
        retention_seconds: int = RAW_RETENTION_SECONDS,
    ) -> int:
        if retention_seconds <= 0:
            raise ValueError("retention_seconds must be positive")
        cutoff = int(time.time() if now is None else now) - retention_seconds
        with self._connect() as db:
            return db.execute(
                "DELETE FROM unsupported_targets WHERE last_seen_at < ?", (cutoff,)
            ).rowcount


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage unsupported goster.me targets")
    subparsers = parser.add_subparsers(dest="command", required=True)
    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--limit", type=int, default=50)
    subparsers.add_parser("purge")
    args = parser.parse_args()
    store = UnsupportedTargetStore()
    if args.command == "list":
        for target in store.list_targets(limit=args.limit):
            print(json.dumps(target, ensure_ascii=False, separators=(",", ":")))
    else:
        print(f"purged={store.purge()}")


if __name__ == "__main__":
    main()
