"""Subscribes to news.new and emits per-user notification jobs to notifications.outbound."""

from __future__ import annotations

import json
import logging

import redis.asyncio as aioredis
from sqlalchemy import select

from ..db import SessionLocal
from ..models import Device, WatchlistItem
from ..pipeline.store import NEWS_CHANNEL

log = logging.getLogger(__name__)

OUTBOUND_LIST = "notifications.outbound"


async def _match_users(payload: dict) -> list[tuple[int, str]]:
    """Return list of (user_id, matched_value) for everyone whose watchlist matches the news."""
    title = (payload.get("title") or "").lower()
    summary = (payload.get("summary") or "").lower()
    haystack = f"{title} {summary}"
    tickers = {t.upper() for t in payload.get("tickers", [])}

    matched: list[tuple[int, str]] = []
    async with SessionLocal() as session:
        items = (await session.execute(select(WatchlistItem))).scalars().all()
        for w in items:
            v = w.value.strip()
            if not v:
                continue
            if w.kind == "ticker":
                if v.upper() in tickers:
                    matched.append((w.user_id, v.upper()))
            elif w.kind == "keyword":
                if v.lower() in haystack:
                    matched.append((w.user_id, v))
    # dedup by user
    seen: dict[int, str] = {}
    for u, m in matched:
        seen.setdefault(u, m)
    return list(seen.items())


async def _enqueue(redis: aioredis.Redis, user_id: int, matched: str, payload: dict) -> None:
    async with SessionLocal() as session:
        rows = (await session.execute(select(Device).where(Device.user_id == user_id))).scalars().all()
    if not rows:
        return
    job = {
        "tokens": [d.fcm_token for d in rows],
        "title": f"📈 {matched}: {payload.get('source')}",
        "body": payload.get("title", "")[:200],
        "data": {
            "url": payload.get("url", ""),
            "news_id": str(payload.get("id", "")),
            "matched": matched,
        },
    }
    await redis.rpush(OUTBOUND_LIST, json.dumps(job))


async def run(redis: aioredis.Redis) -> None:
    pubsub = redis.pubsub()
    await pubsub.subscribe(NEWS_CHANNEL)
    log.info("matcher subscribed to %s", NEWS_CHANNEL)
    async for msg in pubsub.listen():
        if msg.get("type") != "message":
            continue
        try:
            payload = json.loads(msg["data"])
        except (TypeError, ValueError):
            continue
        for user_id, matched in await _match_users(payload):
            await _enqueue(redis, user_id, matched, payload)
