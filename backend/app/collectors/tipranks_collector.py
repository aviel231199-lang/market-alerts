"""TipRanks collector — polls analyst ratings, price targets and news.

TipRanks exposes a public-facing data API used by their website.
This collector uses the same endpoints the browser uses (no paid API key needed
for the basic tier). For production use, consider their official Partner API.

Endpoints used:
  GET https://www.tipranks.com/api/stocks/getData/?name=AAPL
  GET https://www.tipranks.com/api/stocks/getNews/?ticker=AAPL&numberOfDays=1
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx
import redis.asyncio as aioredis
from sqlalchemy import select

from ..db import SessionLocal
from ..models import WatchlistItem
from ..pipeline.store import RawNews, ingest

log = logging.getLogger(__name__)

BASE = "https://www.tipranks.com/api/stocks"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.tipranks.com/",
}
POLL_SECONDS = 300  # every 5 minutes per ticker


async def _unique_tickers() -> list[str]:
    async with SessionLocal() as session:
        rows = (
            await session.execute(select(WatchlistItem).where(WatchlistItem.kind == "ticker"))
        ).scalars().all()
        return list({r.value.upper() for r in rows})


async def _fetch_analyst_data(client: httpx.AsyncClient, ticker: str) -> dict | None:
    try:
        r = await client.get(f"{BASE}/getData/", params={"name": ticker}, timeout=15)
        if r.status_code == 200:
            return r.json()
    except httpx.HTTPError as e:
        log.warning("tipranks getData failed ticker=%s err=%s", ticker, e)
    return None


async def _fetch_news(client: httpx.AsyncClient, ticker: str) -> list[dict]:
    try:
        r = await client.get(f"{BASE}/getNews/", params={"ticker": ticker, "numberOfDays": 1}, timeout=15)
        if r.status_code == 200:
            return r.json().get("news", [])
    except httpx.HTTPError:
        pass
    return []


def _parse_consensus(data: dict) -> str:
    """Return human-readable analyst consensus string."""
    consensus_map = {1: "Strong Sell", 2: "Sell", 3: "Hold", 4: "Buy", 5: "Strong Buy"}
    rating = data.get("consensus", {})
    score = rating.get("score") or 0
    pt = data.get("priceTarget", {}).get("priceTarget")
    upside = data.get("priceTarget", {}).get("upside")
    label = consensus_map.get(round(score), "Hold")
    parts = [f"TipRanks Consensus: {label}"]
    if pt:
        parts.append(f"Price Target: ${pt:.2f}")
    if upside is not None:
        parts.append(f"Upside: {upside:+.1f}%")
    return " · ".join(parts)


async def _process_ticker(client: httpx.AsyncClient, redis: aioredis.Redis, ticker: str) -> None:
    data = await _fetch_analyst_data(client, ticker)
    if data:
        summary = _parse_consensus(data)
        news_items = await _fetch_news(client, ticker)
        # Ingest analyst summary as a synthetic news item
        await ingest(redis, RawNews(
            source="TipRanks",
            title=f"{ticker}: {summary}",
            url=f"https://www.tipranks.com/stocks/{ticker.lower()}/forecast",
            summary=_build_detail(data),
            tickers=[ticker],
        ))
        # Ingest actual news articles
        for item in news_items[:5]:
            url = item.get("url", "")
            title = item.get("title", "").strip()
            if not title or not url:
                continue
            await ingest(redis, RawNews(
                source=f"TipRanks/News",
                title=title,
                url=url,
                summary=item.get("description"),
                tickers=[ticker],
            ))


def _build_detail(data: dict) -> str:
    lines = []
    analysts = data.get("numOfAnalysts")
    if analysts:
        lines.append(f"{analysts} analysts covering this stock")
    buys = data.get("numBuy", 0)
    holds = data.get("numHold", 0)
    sells = data.get("numSell", 0)
    if buys or holds or sells:
        lines.append(f"Ratings: {buys} Buy / {holds} Hold / {sells} Sell")
    best_pt = data.get("bestPriceTarget", {})
    if best_pt.get("priceTarget"):
        lines.append(f"Best Analyst PT: ${best_pt['priceTarget']:.2f}")
    return " · ".join(lines) if lines else None


async def run(redis: aioredis.Redis) -> None:
    log.info("tipranks collector starting")
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        while True:
            tickers = await _unique_tickers()
            if tickers:
                log.info("tipranks polling %d tickers", len(tickers))
                await asyncio.gather(
                    *(_process_ticker(client, redis, t) for t in tickers),
                    return_exceptions=True,
                )
            await asyncio.sleep(POLL_SECONDS)
