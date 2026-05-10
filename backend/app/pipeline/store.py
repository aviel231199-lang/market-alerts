"""Normalize → dedup → persist → publish."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import redis.asyncio as aioredis
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..db import SessionLocal
from ..models import NewsItem

log = logging.getLogger(__name__)

NEWS_CHANNEL = "news.new"
DEDUP_KEY = "news:dedup"
TICKER_RE = re.compile(r"\$?\b([A-Z]{1,5})\b")


@dataclass
class RawNews:
    source: str
    title: str
    url: str
    summary: str | None = None
    published_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tickers: list[str] = field(default_factory=list)

    def hash(self) -> str:
        key = f"{self.title.strip().lower()}|{self.url.strip()}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()


def extract_tickers(text: str) -> list[str]:
    blacklist = {"A", "I", "AM", "PM", "USD", "EU", "UK", "US", "CEO", "CFO", "IPO", "ETF", "FED", "GDP"}
    found = {m for m in TICKER_RE.findall(text or "") if m not in blacklist and len(m) >= 2}
    return sorted(found)


async def ingest(redis: aioredis.Redis, raw: RawNews) -> bool:
    """Returns True if the item was new and stored."""
    if not raw.tickers:
        raw.tickers = extract_tickers(f"{raw.title} {raw.summary or ''}")

    h = raw.hash()
    # SADD returns 1 if new
    is_new = await redis.sadd(DEDUP_KEY, h)
    if not is_new:
        return False
    await redis.expire(DEDUP_KEY, 60 * 60 * 24)

    async with SessionLocal() as session:
        stmt = (
            pg_insert(NewsItem)
            .values(
                source=raw.source,
                title=raw.title,
                summary=raw.summary,
                url=raw.url,
                tickers=raw.tickers,
                published_at=raw.published_at,
                hash=h,
            )
            .on_conflict_do_nothing(index_elements=["hash"])
            .returning(NewsItem.id)
        )
        result = await session.execute(stmt)
        row = result.first()
        await session.commit()
        if row is None:
            return False
        news_id = row[0]

    payload = {**asdict(raw), "id": news_id, "published_at": raw.published_at.isoformat()}
    await redis.publish(NEWS_CHANNEL, json.dumps(payload))
    log.info("ingested news id=%s source=%s tickers=%s", news_id, raw.source, raw.tickers)
    return True
