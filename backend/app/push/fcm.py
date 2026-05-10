"""FCM push worker — drains notifications.outbound and sends via firebase-admin."""

from __future__ import annotations

import asyncio
import json
import logging
import os

import redis.asyncio as aioredis

from ..config import settings
from ..matcher.engine import OUTBOUND_LIST

log = logging.getLogger(__name__)

_initialized = False


def _init() -> None:
    global _initialized
    if _initialized:
        return
    import firebase_admin
    from firebase_admin import credentials

    if settings.fcm_credentials_file and os.path.exists(settings.fcm_credentials_file):
        cred = credentials.Certificate(settings.fcm_credentials_file)
        firebase_admin.initialize_app(cred)
    else:
        firebase_admin.initialize_app()
    _initialized = True


def _send_sync(tokens: list[str], title: str, body: str, data: dict) -> None:
    from firebase_admin import messaging

    msg = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(title=title, body=body),
        data={k: str(v) for k, v in data.items()},
    )
    messaging.send_each_for_multicast(msg)


async def run(redis: aioredis.Redis) -> None:
    if not settings.fcm_credentials_file:
        log.warning("FCM_CREDENTIALS_FILE not set; push worker idling")
        while True:
            await asyncio.sleep(3600)

    _init()
    log.info("fcm worker started")
    while True:
        item = await redis.blpop(OUTBOUND_LIST, timeout=0)
        if item is None:
            continue
        _, raw = item
        try:
            job = json.loads(raw)
            await asyncio.to_thread(_send_sync, job["tokens"], job["title"], job["body"], job.get("data", {}))
        except Exception:
            log.exception("fcm send failed")
