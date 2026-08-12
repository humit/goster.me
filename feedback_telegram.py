#!/usr/bin/env python3

from __future__ import annotations

import http.client
import json
import os
import urllib.parse

from datetime import datetime, timezone

from feedback import FeedbackStore


TELEGRAM_TEXT_LIMIT = 4096
SAFE_TEXT_LIMIT = 3900
DEFAULT_BATCH_LIMIT = 20


def format_notification(message: dict[str, object]) -> str:
    created = datetime.fromtimestamp(
        int(message["created_at"]), tz=timezone.utc
    ).strftime("%Y-%m-%d %H:%M UTC")
    prefix = (
        "Yeni goster.me iletişim mesajı\n"
        f"Kategori: {message['category']}\n"
        f"Zaman: {created}\n"
        f"Makbuz: {message['id']}\n\n"
    )
    body = str(message["message"])
    full = prefix + body
    if len(full) <= SAFE_TEXT_LIMIT:
        return full
    suffix = "\n\n[Mesaj kısaltıldı; tamamı tools/goster feedback list ile görülebilir.]"
    return full[: SAFE_TEXT_LIMIT - len(suffix)] + suffix


def send_message(token: str, chat_id: str, text: str) -> None:
    if not token or not chat_id:
        raise ValueError("Telegram token and chat ID are required")
    if len(text) > TELEGRAM_TEXT_LIMIT:
        raise ValueError("Telegram message exceeds the platform limit")
    body = urllib.parse.urlencode({"chat_id": chat_id, "text": text})
    connection = http.client.HTTPSConnection("api.telegram.org", timeout=15)
    try:
        connection.request(
            "POST",
            f"/bot{token}/sendMessage",
            body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = connection.getresponse()
        payload = response.read()
    finally:
        connection.close()
    try:
        result = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Telegram returned an invalid response") from exc
    if response.status != 200 or result.get("ok") is not True:
        raise RuntimeError(f"Telegram delivery failed with HTTP {response.status}")


def notify_pending(
    store: FeedbackStore,
    *,
    token: str,
    chat_id: str,
    limit: int = DEFAULT_BATCH_LIMIT,
) -> int:
    delivered = 0
    for message in store.pending_notifications(limit=limit):
        send_message(token, chat_id, format_notification(message))
        if not store.mark_notified(str(message["id"])):
            raise RuntimeError("Feedback disappeared after Telegram delivery")
        delivered += 1
    return delivered


def main() -> None:
    token = os.environ.get("GOSTER_TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("GOSTER_TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        raise SystemExit("Telegram notification configuration is missing")
    delivered = notify_pending(FeedbackStore(), token=token, chat_id=chat_id)
    print(f"telegram_feedback_delivered={delivered}")


if __name__ == "__main__":
    main()
