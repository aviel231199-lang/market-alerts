"""Dashboard — indices snapshot + personalized feed for home screen."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import NewsItem, User, WatchlistItem
from ..security import current_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Free indices from Yahoo Finance query API
INDICES = {
    "S&P 500": "^GSPC",
    "NASDAQ": "^IXIC",
    "Dow Jones": "^DJI",
    "VIX": "^VIX",
    "תל אביב 35": "^TA35.TA",
    "תל אביב 125": "^TA125.TA",
    "EUR/USD": "EURUSD=X",
    "USD/ILS": "ILS=X",
    "Gold": "GC=F",
    "Oil (WTI)": "CL=F",
    "BTC": "BTC-USD",
}

_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbols}&fields=regularMarketPrice,regularMarketChangePercent,regularMarketTime"


async def _fetch_indices() -> list[dict]:
    symbols = ",".join(INDICES.values())
    try:
        async with httpx.AsyncClient(timeout=8, headers={"User-Agent": "MarketAlerts/1.0"}) as client:
            r = await client.get(_QUOTE_URL.format(symbols=symbols))
            r.raise_for_status()
            results = r.json().get("quoteResponse", {}).get("result", [])
    except Exception as e:
        log.warning("indices fetch failed: %s", e)
        return []

    label_by_sym = {v: k for k, v in INDICES.items()}
    out = []
    for q in results:
        sym = q.get("symbol", "")
        price = q.get("regularMarketPrice")
        chg = q.get("regularMarketChangePercent")
        if price is None:
            continue
        out.append({
            "label": label_by_sym.get(sym, sym),
            "symbol": sym,
            "price": round(price, 4),
            "change_pct": round(chg, 2) if chg is not None else None,
            "direction": "up" if (chg or 0) > 0 else "down" if (chg or 0) < 0 else "flat",
        })
    return out


@router.get("")
async def dashboard(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Home screen data: indices + personalized top news."""

    # Fetch indices + personalized news concurrently
    watch_rows, indices = await asyncio.gather(
        session.execute(select(WatchlistItem).where(WatchlistItem.user_id == user.id)),
        _fetch_indices(),
    )
    watchlist = watch_rows.scalars().all()
    keywords = [w.value.lower() for w in watchlist if w.kind == "keyword"]
    tickers = [w.value.upper() for w in watchlist if w.kind == "ticker"]

    # Last 24h personalized news
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    from sqlalchemy import or_
    stmt = (
        select(NewsItem)
        .where(NewsItem.published_at >= since)
        .order_by(NewsItem.published_at.desc())
        .limit(20)
    )
    filters = []
    if tickers:
        filters.append(NewsItem.tickers.overlap(tickers))
    for kw in keywords:
        filters.append(NewsItem.title.ilike(f"%{kw}%"))
    if filters:
        stmt = stmt.where(or_(*filters))

    # Premium gate
    if not user.is_premium:
        stmt = stmt.where(NewsItem.is_premium.is_(False))

    news_rows = (await session.execute(stmt)).scalars().all()

    return {
        "indices": indices,
        "personalized_news": [
            {
                "id": n.id,
                "source": n.source,
                "title": n.title,
                "url": n.url,
                "tickers": n.tickers,
                "published_at": n.published_at.isoformat(),
                "is_premium": n.is_premium,
            }
            for n in news_rows
        ],
        "watchlist_tickers": tickers,
        "is_premium": user.is_premium,
    }
