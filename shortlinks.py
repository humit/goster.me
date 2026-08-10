#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import time

from dataclasses import asdict
from pathlib import Path

from adapters import ResolvedContent


# Deliberately excludes characters that are easy to confuse when a code is
# read from another screen or spoken aloud: 0/O, 1/I/l, 2/Z and 5/S.
SHORT_CODE_ALPHABET = "abcdefghjkmnpqrstuvwxy346789"
SHORT_CODE_LENGTH = int(
    os.environ.get("GOSTER_SHORT_CODE_LENGTH", "6")
)
DEFAULT_TTL_SECONDS = int(
    os.environ.get("GOSTER_LINK_TTL_SECONDS", str(14 * 24 * 60 * 60))
)
DATABASE_PATH = Path(
    os.environ.get(
        "GOSTER_DATABASE",
        "/var/lib/goster.me/goster.sqlite3",
    )
)


class ShortLinkStore:
    def __init__(
        self,
        path: str | Path = DATABASE_PATH,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        code_length: int = SHORT_CODE_LENGTH,
    ) -> None:
        self.path = Path(path)
        self.ttl_seconds = ttl_seconds
        self.code_length = code_length

        if self.code_length < 4:
            raise ValueError("Short-code length must be at least 4.")

        if self.ttl_seconds <= 0:
            raise ValueError("TTL must be positive.")

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=10,
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS short_links (
                    code TEXT PRIMARY KEY,
                    source_url TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    last_accessed_at INTEGER,
                    access_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            db.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    short_links_expires_at_idx
                ON short_links(expires_at)
                """
            )

    def _new_code(self) -> str:
        return "".join(
            secrets.choice(SHORT_CODE_ALPHABET)
            for _ in range(self.code_length)
        )

    @staticmethod
    def _serialize(item: ResolvedContent) -> str:
        return json.dumps(
            asdict(item),
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @staticmethod
    def _deserialize(value: str) -> ResolvedContent:
        data = json.loads(value)

        # JSON has no tuple type; keep the adapter model stable after reload.
        data["content_urls"] = tuple(
            data.get("content_urls") or ()
        )

        return ResolvedContent(**data)

    def save(
        self,
        item: ResolvedContent,
        *,
        now: int | None = None,
    ) -> str:
        timestamp = int(
            time.time()
            if now is None
            else now
        )
        expires_at = timestamp + self.ttl_seconds
        payload = self._serialize(item)

        # Collision probability is tiny, but the database remains the source
        # of truth and we retry rather than assuming uniqueness.
        for _ in range(32):
            code = self._new_code()

            try:
                with self._connect() as db:
                    db.execute(
                        """
                        INSERT INTO short_links (
                            code,
                            source_url,
                            payload_json,
                            created_at,
                            expires_at
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            code,
                            item.source_url,
                            payload,
                            timestamp,
                            expires_at,
                        ),
                    )
                return code
            except sqlite3.IntegrityError:
                continue

        raise RuntimeError(
            "Could not allocate a unique short code."
        )

    def get(
        self,
        code: str,
        *,
        now: int | None = None,
        touch: bool = True,
    ) -> ResolvedContent | None:
        normalized = code.strip().lower()

        if (
            len(normalized) != self.code_length
            or any(
                ch not in SHORT_CODE_ALPHABET
                for ch in normalized
            )
        ):
            return None

        timestamp = int(
            time.time()
            if now is None
            else now
        )

        with self._connect() as db:
            row = db.execute(
                """
                SELECT payload_json, expires_at
                FROM short_links
                WHERE code = ?
                """,
                (normalized,),
            ).fetchone()

            if row is None:
                return None

            if row["expires_at"] <= timestamp:
                db.execute(
                    "DELETE FROM short_links WHERE code = ?",
                    (normalized,),
                )
                return None

            if touch:
                db.execute(
                    """
                    UPDATE short_links
                    SET
                        last_accessed_at = ?,
                        access_count = access_count + 1
                    WHERE code = ?
                    """,
                    (timestamp, normalized),
                )

        return self._deserialize(
            row["payload_json"]
        )

    def expires_at(
        self,
        code: str,
    ) -> int | None:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT expires_at
                FROM short_links
                WHERE code = ?
                """,
                (code.strip().lower(),),
            ).fetchone()

        if row is None:
            return None

        return int(row["expires_at"])

    def purge_expired(
        self,
        *,
        now: int | None = None,
    ) -> int:
        timestamp = int(
            time.time()
            if now is None
            else now
        )

        with self._connect() as db:
            cursor = db.execute(
                """
                DELETE FROM short_links
                WHERE expires_at <= ?
                """,
                (timestamp,),
            )

        return cursor.rowcount
