#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sqlite3
import time

from pathlib import Path

from shortlinks import DATABASE_MAX_BYTES, DATABASE_PATH


MESSAGE_MIN_LENGTH = 3
MESSAGE_MAX_LENGTH = 2000
RAW_RETENTION_SECONDS = int(
    os.environ.get("GOSTER_FEEDBACK_RETENTION_SECONDS", str(90 * 24 * 60 * 60))
)
MAX_ROWS = int(os.environ.get("GOSTER_FEEDBACK_MAX_ROWS", "2000"))
TARGET_ROWS = int(os.environ.get("GOSTER_FEEDBACK_TARGET_ROWS", "1800"))
CATEGORIES = frozenset({"problem", "suggestion", "other"})
RECEIPT_RE = re.compile(r"^[a-f0-9]{12}$")


def normalize_submission(category: str, message: str, website: str = "") -> tuple[str, str]:
    """Validate public form fields. ``website`` is an invisible spam trap."""
    if website:
        raise ValueError("Spam trap was filled.")

    normalized_category = category.strip().lower()
    if normalized_category not in CATEGORIES:
        raise ValueError("Unsupported feedback category.")

    normalized_message = message.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not MESSAGE_MIN_LENGTH <= len(normalized_message) <= MESSAGE_MAX_LENGTH:
        raise ValueError("Feedback message has an invalid length.")

    if any(ord(char) < 32 and char not in {"\n", "\t"} for char in normalized_message):
        raise ValueError("Feedback message contains control characters.")

    return normalized_category, normalized_message


class FeedbackStore:
    """Private, bounded feedback storage without visitor identifiers."""

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
                CREATE TABLE IF NOT EXISTS feedback_messages (
                    id TEXT PRIMARY KEY,
                    created_at INTEGER NOT NULL,
                    category TEXT NOT NULL
                        CHECK(category IN ('problem', 'suggestion', 'other')),
                    message TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'unread'
                        CHECK(status IN ('unread', 'reviewed')),
                    reviewed_at INTEGER
                )
                """
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS feedback_created_at_idx "
                "ON feedback_messages(created_at)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS feedback_status_idx "
                "ON feedback_messages(status, created_at)"
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
        rows = int(db.execute("SELECT COUNT(*) FROM feedback_messages").fetchone()[0])
        if rows < self.max_rows:
            return

        trim_count = max(1, rows - self.target_rows + 1)
        db.execute(
            """
            DELETE FROM feedback_messages
            WHERE id IN (
                SELECT id FROM feedback_messages
                ORDER BY created_at ASC
                LIMIT ?
            )
            """,
            (trim_count,),
        )

    def submit(
        self,
        category: str,
        message: str,
        *,
        website: str = "",
        now: int | None = None,
    ) -> str:
        normalized_category, normalized_message = normalize_submission(
            category, message, website
        )
        timestamp = int(time.time() if now is None else now)

        for _ in range(16):
            receipt = secrets.token_hex(6)
            try:
                with self._connect() as db:
                    self._enforce_row_quota(db)
                    db.execute(
                        """
                        INSERT INTO feedback_messages (
                            id, created_at, category, message
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (receipt, timestamp, normalized_category, normalized_message),
                    )
                return receipt
            except sqlite3.IntegrityError:
                continue

        raise RuntimeError("Could not allocate a feedback receipt.")

    def list_messages(
        self,
        *,
        status: str = "unread",
        limit: int = 50,
    ) -> list[dict[str, object]]:
        if status not in {"unread", "reviewed", "all"}:
            raise ValueError("Unsupported feedback status.")
        if limit <= 0 or limit > 500:
            raise ValueError("limit must be between 1 and 500")

        query = (
            "SELECT id, created_at, category, message, status, reviewed_at "
            "FROM feedback_messages"
        )
        params: list[object] = []
        if status != "all":
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute(query, params)]

    def mark_reviewed(self, receipt: str, *, now: int | None = None) -> bool:
        normalized = receipt.strip().lower()
        if not RECEIPT_RE.fullmatch(normalized):
            return False
        timestamp = int(time.time() if now is None else now)
        with self._connect() as db:
            updated = db.execute(
                """
                UPDATE feedback_messages
                SET status = 'reviewed', reviewed_at = ?
                WHERE id = ?
                """,
                (timestamp, normalized),
            ).rowcount
        return updated == 1

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
                "DELETE FROM feedback_messages WHERE created_at < ?", (cutoff,)
            ).rowcount


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage private goster.me feedback")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List feedback as JSON lines")
    list_parser.add_argument(
        "--status",
        choices=("unread", "reviewed", "all"),
        default="unread",
    )
    list_parser.add_argument("--limit", type=int, default=50)

    ack_parser = subparsers.add_parser("ack", help="Mark one message as reviewed")
    ack_parser.add_argument("receipt")

    subparsers.add_parser("purge", help="Purge messages past the retention window")
    args = parser.parse_args()
    store = FeedbackStore()

    if args.command == "list":
        for message in store.list_messages(status=args.status, limit=args.limit):
            print(json.dumps(message, ensure_ascii=False, separators=(",", ":")))
    elif args.command == "ack":
        if not store.mark_reviewed(args.receipt):
            parser.error("feedback receipt not found")
        print(f"reviewed={args.receipt.lower()}")
    else:
        print(f"purged={store.purge()}")


if __name__ == "__main__":
    main()
