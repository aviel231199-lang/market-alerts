"""Telethon listener — joins configured channels and pushes messages into the pipeline."""

from __future__ import annotations

import asyncio
import logging
from datetime import timezone

import redis.asyncio as aioredis
from sqlalchemy import select
from telethon import TelegramClient, events

from ..config import settings
from ..db import SessionLocal
from ..models import TelegramSource
from ..pipeline.store import RawNews, ingest

log = logging.getLogger(__name__)


async def _active_channels() -> list[str]:
    async with SessionLocal() as session:
        rows = (await session.execute(select(TelegramSource).where(TelegramSource.active.is_(True)))).scalars().all()
        return [r.channel for r in rows]


async def run(redis: aioredis.Redis) -> None:
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        log.warning("Telegram credentials not configured; skipping telegram collector")
        return

    client = TelegramClient(settings.telegram_session, settings.telegram_api_id, settings.telegram_api_hash)
    await client.start()
    log.info("telegram collector started")

    channels = await _active_channels()

    @client.on(events.NewMessage(chats=channels or None))
    async def _handler(event):
        msg = event.message
        text = (msg.message or "").strip()
        if not text:
            return
        title = text.splitlines()[0][:280]
        chat = await event.get_chat()
        chan_name = getattr(chat, "username", None) or getattr(chat, "title", "telegram")
        url = f"https://t.me/{chan_name}/{msg.id}" if getattr(chat, "username", None) else ""
        published = msg.date.astimezone(timezone.utc) if msg.date else None
        raw = RawNews(
            source=f"tg:{chan_name}",
            title=title,
            url=url or f"tg://message?chat={chan_name}&id={msg.id}",
            summary=text if text != title else None,
            published_at=published,
        )
        await ingest(redis, raw)

    # Periodically refresh subscribed channel list (every 5 min)
    while True:
        await asyncio.sleep(300)
        # Telethon's NewMessage filter is fixed at registration; for simplicity,
        # process restart picks up newly added channels. Could be enhanced with
        # per-channel handlers + dynamic registration.
