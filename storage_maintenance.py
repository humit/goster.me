#!/usr/bin/env python3

from __future__ import annotations

import os
import sqlite3
import time

from pathlib import Path

from analytics import RAW_RETENTION_SECONDS
from feedback import RAW_RETENTION_SECONDS as FEEDBACK_RETENTION_SECONDS
from unsupported import RAW_RETENTION_SECONDS as UNSUPPORTED_RETENTION_SECONDS


DATABASE_PATH = Path(
    os.environ.get(
        "GOSTER_DATABASE",
        "/var/lib/goster.me/goster.sqlite3",
    )
)
MAX_ROWS = int(os.environ.get("GOSTER_DATABASE_MAX_ROWS", "50000"))
TARGET_ROWS = int(os.environ.get("GOSTER_DATABASE_TARGET_ROWS", "45000"))
MAX_BYTES = int(os.environ.get("GOSTER_DATABASE_MAX_BYTES", str(128 * 1024 * 1024)))


def maintain_database(
    path: str | Path = DATABASE_PATH,
    *,
    now: int | None = None,
    max_rows: int = MAX_ROWS,
    target_rows: int = TARGET_ROWS,
    max_bytes: int = MAX_BYTES,
) -> dict[str, int]:
    db_path = Path(path)

    if max_rows <= 0:
        raise ValueError("max_rows must be positive")

    if target_rows <= 0 or target_rows > max_rows:
        raise ValueError("target_rows must be positive and <= max_rows")

    if max_bytes < 1024 * 1024:
        raise ValueError("max_bytes must be at least 1 MiB")

    timestamp = int(time.time() if now is None else now)

    with sqlite3.connect(db_path, timeout=30) as db:
        page_size = int(db.execute("PRAGMA page_size").fetchone()[0])
        max_pages = max(1, max_bytes // page_size)
        current_pages = int(db.execute("PRAGMA page_count").fetchone()[0])

        if current_pages > max_pages:
            raise RuntimeError(
                f"database already exceeds configured cap: {current_pages * page_size} > {max_bytes}"
            )

        # max_page_count is connection-scoped in practice. Applying it here
        # protects this maintenance connection; ShortLinkStore applies the same
        # cap on every application connection where new rows can be written.
        applied_max_pages = int(
            db.execute(f"PRAGMA max_page_count={max_pages}").fetchone()[0]
        )

        expired = db.execute(
            "DELETE FROM short_links WHERE expires_at <= ?",
            (timestamp,),
        ).rowcount

        analytics_purged = 0
        analytics_table = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'analytics_events'"
        ).fetchone()
        if analytics_table is not None:
            analytics_purged = db.execute(
                "DELETE FROM analytics_events WHERE occurred_at < ?",
                (timestamp - RAW_RETENTION_SECONDS,),
            ).rowcount

        feedback_purged = 0
        feedback_table = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'feedback_messages'"
        ).fetchone()
        if feedback_table is not None:
            feedback_purged = db.execute(
                "DELETE FROM feedback_messages WHERE created_at < ?",
                (timestamp - FEEDBACK_RETENTION_SECONDS,),
            ).rowcount

        unsupported_purged = 0
        unsupported_table = db.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type = 'table' AND name = 'unsupported_targets'"
        ).fetchone()
        if unsupported_table is not None:
            unsupported_purged = db.execute(
                "DELETE FROM unsupported_targets WHERE last_seen_at < ?",
                (timestamp - UNSUPPORTED_RETENTION_SECONDS,),
            ).rowcount

        rows = int(db.execute("SELECT COUNT(*) FROM short_links").fetchone()[0])
        trimmed = 0

        if rows > max_rows:
            trim_count = rows - target_rows
            cursor = db.execute(
                """
                DELETE FROM short_links
                WHERE code IN (
                    SELECT code
                    FROM short_links
                    ORDER BY
                        COALESCE(last_accessed_at, created_at) ASC,
                        created_at ASC
                    LIMIT ?
                )
                """,
                (trim_count,),
            )
            trimmed = cursor.rowcount

        remaining = int(db.execute("SELECT COUNT(*) FROM short_links").fetchone()[0])
        page_count = int(db.execute("PRAGMA page_count").fetchone()[0])
        freelist_count = int(db.execute("PRAGMA freelist_count").fetchone()[0])

    return {
        "expired": expired,
        "analytics_purged": analytics_purged,
        "feedback_purged": feedback_purged,
        "unsupported_purged": unsupported_purged,
        "trimmed": trimmed,
        "remaining": remaining,
        "page_size": page_size,
        "page_count": page_count,
        "freelist_count": freelist_count,
        "max_pages_this_connection": applied_max_pages,
        "logical_bytes": page_count * page_size,
    }


if __name__ == "__main__":
    stats = maintain_database()
    print(
        "goster storage maintenance "
        + " ".join(f"{key}={value}" for key, value in stats.items()),
        flush=True,
    )
