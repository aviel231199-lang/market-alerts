from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import NewsItem, User, WatchlistItem
from ..schemas import NewsOut
from ..security import current_user

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=list[NewsOut])
async def list_news(
    since: datetime | None = None,
    limit: int = Query(50, le=200),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[NewsItem]:
    watch = (await session.execute(select(WatchlistItem).where(WatchlistItem.user_id == user.id))).scalars().all()
    keywords = [w.value.lower() for w in watch if w.kind == "keyword"]
    tickers = [w.value.upper() for w in watch if w.kind == "ticker"]

    stmt = select(NewsItem).order_by(NewsItem.published_at.desc()).limit(limit)
    if since is not None:
        stmt = stmt.where(NewsItem.published_at >= since)
    filters = []
    if tickers:
        filters.append(NewsItem.tickers.overlap(tickers))
    for kw in keywords:
        filters.append(NewsItem.title.ilike(f"%{kw}%"))
    if filters:
        stmt = stmt.where(or_(*filters))

    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)
