"""RSS poller. Uses ETag/Last-Modified via Redis to skip unchanged feeds."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from time import mktime

import feedparser
import httpx
import redis.asyncio as aioredis

from ..config import settings
from ..pipeline.store import RawNews, ingest

log = logging.getLogger(__name__)

FEEDS: list[tuple[str, str]] = [
    # Google News Finance
    ("Google-Markets", "https://news.google.com/rss/search?q=stock+market+finance&hl=en-US&gl=US&ceid=US:en"),
    ("Google-Earnings", "https://news.google.com/rss/search?q=earnings+report+beats+misses&hl=en-US&gl=US&ceid=US:en"),
    # Existing feeds
    ("Investing", "https://www.investing.com/rss/news_25.rss"),
    ("Investing-Stocks", "https://www.investing.com/rss/news_285.rss"),
    ("MarketWatch-TopStories", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("MarketWatch-Markets", "https://feeds.content.dowjones.io/public/rss/mw_marketpulse"),
    ("CNBC-TopNews", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
    ("CNBC-Markets", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069"),
    ("Yahoo-Finance", "https://finance.yahoo.com/news/rssindex"),
    ("Reuters-Business", "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best"),
    ("SeekingAlpha", "https://seekingalpha.com/market_currents.xml"),
    ("WSJ-Markets", "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain"),
    ("Bloomberg-Markets", "https://feeds.bloomberg.com/markets/news.rss"),
    # ── Israeli sources ──────────────────────────────────────────────────
    # Maya — TASE official disclosure filings
    ("Maya-TASE", "https://maya.tase.co.il/rss/RssFeed.aspx?feedType=3"),
    # Calcalist (כלכליסט) — leading Israeli financial news
    ("Calcalist", "https://www.calcalist.co.il/rss/AjaxPage,7340,L-1,00.xml"),
    # TheMarker (הארץ כלכלה)
    ("TheMarker", "https://www.themarker.com/cmlink/1.4688995"),
    # Globes — ישראל עסקים
    ("Globes", "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=585"),
    # Ynet Money
    ("Ynet-Money", "https://www.ynet.co.il/Integration/StoryRss2.xml?catid=5"),
    # N12 / ערוץ 12 כלכלה (Channel 12 economy)
    ("N12-Economy", "https://www.mako.co.il/rss/31750a2610f26110VgnVCM1000004463fa90RCRD.xml"),
]


async def _fetch(client: httpx.AsyncClient, redis: aioredis.Redis, source: str, url: str) -> None:
    cache_key = f"rss:cache:{url}"
    cached = await redis.hgetall(cache_key)
    headers = {"User-Agent": "MarketAlerts/1.0"}
    if cached.get(b"etag"):
        headers["If-None-Match"] = cached[b"etag"].decode()
    if cached.get(b"last_modified"):
        headers["If-Modified-Since"] = cached[b"last_modified"].decode()

    try:
        resp = await client.get(url, headers=headers, timeout=15)
    except httpx.HTTPError as e:
        log.warning("rss fetch failed source=%s err=%s", source, e)
        return

    if resp.status_code == 304:
        return
    if resp.status_code != 200:
        log.warning("rss bad status source=%s status=%s", source, resp.status_code)
        return

    new_headers = {}
    if "etag" in resp.headers:
        new_headers["etag"] = resp.headers["etag"]
    if "last-modified" in resp.headers:
        new_headers["last_modified"] = resp.headers["last-modified"]
    if new_headers:
        await redis.hset(cache_key, mapping=new_headers)
        await redis.expire(cache_key, 60 * 60 * 24 * 7)

    parsed = feedparser.parse(resp.content)
    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue
        summary = entry.get("summary") or entry.get("description")
        published_at = datetime.now(timezone.utc)
        if entry.get("published_parsed"):
            published_at = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
        elif entry.get("updated_parsed"):
            published_at = datetime.fromtimestamp(mktime(entry.updated_parsed), tz=timezone.utc)

        await ingest(redis, RawNews(source=source, title=title, url=link, summary=summary, published_at=published_at))


async def run(redis: aioredis.Redis) -> None:
    log.info("rss collector starting; %d feeds, poll=%ds", len(FEEDS), settings.rss_poll_seconds)
    async with httpx.AsyncClient(follow_redirects=True) as client:
        while True:
            await asyncio.gather(*(_fetch(client, redis, s, u) for s, u in FEEDS), return_exceptions=True)
            await asyncio.sleep(settings.rss_poll_seconds)
