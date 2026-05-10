"""Finnhub WebSocket news collector (free tier).

Free tier: real-time news for US markets.
Get a free API key at https://finnhub.io
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis
import websockets

from ..config import settings
from ..pipeline.store import RawNews, ingest

log = logging.getLogger(__name__)

FINNHUB_WS = "wss://ws.finnhub.io?token={token}"


async def run(redis: aioredis.Redis) -> None:
    if not settings.finnhub_api_key:
        log.warning("FINNHUB_API_KEY not set — skipping Finnhub collector")
        return

    url = FINNHUB_WS.format(token=settings.finnhub_api_key)
    log.info("finnhub collector connecting...")

    while True:
        try:
            async with websockets.connect(url) as ws:
                # Subscribe to news feed
                await ws.send(json.dumps({"type": "subscribe-news", "symbol": ""}))
                log.info("finnhub collector connected")

                async for raw_msg in ws:
                    try:
                        msg = json.loads(raw_msg)
                    except json.JSONDecodeError:
                        continue

                    if msg.get("type") != "news":
                        continue

                    for item in msg.get("data", []):
                        title = (item.get("headline") or "").strip()
                        url_item = (item.get("url") or "").strip()
                        if not title or not url_item:
                            continue

                        ts = item.get("datetime")
                        published_at = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc)
                        tickers = [item["related"]] if item.get("related") else []

                        await ingest(redis, RawNews(
                            source=f"Finnhub/{item.get('source', 'news')}",
                            title=title,
                            url=url_item,
                            summary=item.get("summary"),
                            published_at=published_at,
                            tickers=tickers,
                        ))

        except (websockets.exceptions.WebSocketException, OSError) as e:
            log.warning("finnhub ws disconnected: %s — reconnecting in 10s", e)
            await asyncio.sleep(10)
        except Exception:
            log.exception("finnhub unexpected error — reconnecting in 30s")
            await asyncio.sleep(30)
