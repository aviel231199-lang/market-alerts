"""Trading journal API — log trades, close them, get AI monthly summary."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import extract, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Trade, User
from ..security import current_user

router = APIRouter(prefix="/journal", tags=["journal"])


# ── Schemas ───────────────────────────────────────────────────────────────

class TradeIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    direction: Literal["long", "short"]
    market: str = Field(default="stock", max_length=32)
    entry_price: Decimal
    quantity: Decimal
    entry_at: datetime | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    daily_trend: Literal["bullish", "bearish", "neutral"] | None = None
    reason: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)
    tags: list[str] = []


class CloseTradeIn(BaseModel):
    exit_price: Decimal
    exit_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)


class TradeOut(BaseModel):
    id: int
    ticker: str
    direction: str
    market: str
    entry_price: Decimal
    exit_price: Decimal | None
    quantity: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    entry_at: datetime
    exit_at: datetime | None
    daily_trend: str | None
    reason: str | None
    notes: str | None
    tags: list[str]
    status: str
    pnl: Decimal | None
    pnl_pct: float | None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Routes ────────────────────────────────────────────────────────────────

@router.get("", response_model=list[TradeOut])
async def list_trades(
    status_filter: str | None = Query(None, alias="status"),
    ticker: str | None = None,
    month: int | None = None,
    year: int | None = None,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Trade]:
    stmt = select(Trade).where(Trade.user_id == user.id).order_by(Trade.entry_at.desc())
    if status_filter:
        stmt = stmt.where(Trade.status == status_filter)
    if ticker:
        stmt = stmt.where(Trade.ticker == ticker.upper())
    if month:
        stmt = stmt.where(extract("month", Trade.entry_at) == month)
    if year:
        stmt = stmt.where(extract("year", Trade.entry_at) == year)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


@router.post("", response_model=TradeOut, status_code=status.HTTP_201_CREATED)
async def open_trade(
    data: TradeIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Trade:
    trade = Trade(
        user_id=user.id,
        ticker=data.ticker.upper(),
        direction=data.direction,
        market=data.market,
        entry_price=data.entry_price,
        quantity=data.quantity,
        entry_at=data.entry_at or datetime.now(timezone.utc),
        stop_loss=data.stop_loss,
        take_profit=data.take_profit,
        daily_trend=data.daily_trend,
        reason=data.reason,
        notes=data.notes,
        tags=data.tags,
    )
    session.add(trade)
    await session.commit()
    await session.refresh(trade)
    return trade


@router.put("/{trade_id}/close", response_model=TradeOut)
async def close_trade(
    trade_id: int,
    data: CloseTradeIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Trade:
    trade = (
        await session.execute(select(Trade).where(Trade.id == trade_id, Trade.user_id == user.id))
    ).scalar_one_or_none()
    if not trade:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trade not found")
    if trade.status == "closed":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Trade already closed")
    trade.exit_price = data.exit_price
    trade.exit_at = data.exit_at or datetime.now(timezone.utc)
    trade.status = "closed"
    if data.notes:
        trade.notes = (trade.notes or "") + "\n" + data.notes
    await session.commit()
    await session.refresh(trade)
    return trade


@router.patch("/{trade_id}", response_model=TradeOut)
async def update_trade(
    trade_id: int,
    data: dict,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Trade:
    trade = (
        await session.execute(select(Trade).where(Trade.id == trade_id, Trade.user_id == user.id))
    ).scalar_one_or_none()
    if not trade:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trade not found")
    for k, v in data.items():
        if hasattr(trade, k) and k not in ("id", "user_id"):
            setattr(trade, k, v)
    await session.commit()
    await session.refresh(trade)
    return trade


@router.delete("/{trade_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trade(
    trade_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    trade = (
        await session.execute(select(Trade).where(Trade.id == trade_id, Trade.user_id == user.id))
    ).scalar_one_or_none()
    if trade:
        await session.delete(trade)
        await session.commit()


@router.get("/summary/monthly")
async def monthly_summary(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Generate AI-powered monthly P&L summary."""
    trades = (
        await session.execute(
            select(Trade).where(
                Trade.user_id == user.id,
                Trade.status == "closed",
                extract("month", Trade.entry_at) == month,
                extract("year", Trade.entry_at) == year,
            )
        )
    ).scalars().all()

    if not trades:
        return {"month": month, "year": year, "message": "No closed trades this month", "trades": 0}

    total_pnl = sum(t.pnl or 0 for t in trades)
    winners = [t for t in trades if (t.pnl or 0) > 0]
    losers = [t for t in trades if (t.pnl or 0) <= 0]

    stats = {
        "month": month,
        "year": year,
        "total_trades": len(trades),
        "winners": len(winners),
        "losers": len(losers),
        "win_rate": round(len(winners) / len(trades) * 100, 1),
        "total_pnl": float(total_pnl),
        "avg_winner": float(sum(t.pnl or 0 for t in winners) / len(winners)) if winners else 0,
        "avg_loser": float(sum(t.pnl or 0 for t in losers) / len(losers)) if losers else 0,
        "best_trade": max(trades, key=lambda t: t.pnl or 0, default=None),
        "worst_trade": min(trades, key=lambda t: t.pnl or 0, default=None),
    }

    # AI narrative
    ai_summary = await _ai_monthly_narrative(stats, trades)
    stats["ai_summary"] = ai_summary
    if stats["best_trade"]:
        stats["best_trade"] = {"ticker": stats["best_trade"].ticker, "pnl": float(stats["best_trade"].pnl or 0)}
    if stats["worst_trade"]:
        stats["worst_trade"] = {"ticker": stats["worst_trade"].ticker, "pnl": float(stats["worst_trade"].pnl or 0)}

    return stats


async def _ai_monthly_narrative(stats: dict, trades: list[Trade]) -> str:
    from ..config import settings
    if not settings.anthropic_api_key:
        return "AI summary unavailable — configure ANTHROPIC_API_KEY."

    import anthropic

    trade_lines = "\n".join(
        f"- {t.ticker} ({t.direction.upper()}) | Entry ${t.entry_price} → Exit ${t.exit_price} | "
        f"P&L: ${float(t.pnl or 0):+.2f} ({t.pnl_pct:+.1f}%) | Reason: {t.reason or '—'} | Trend: {t.daily_trend or '—'}"
        for t in trades
    )

    prompt = f"""You are an expert trading coach analyzing a trader's monthly performance.

Month: {stats['month']}/{stats['year']}
Total trades: {stats['total_trades']} | Win rate: {stats['win_rate']}% | Total P&L: ${stats['total_pnl']:+.2f}
Winners: {stats['winners']} | Losers: {stats['losers']}
Avg winner: ${stats['avg_winner']:+.2f} | Avg loser: ${stats['avg_loser']:+.2f}

Trade log:
{trade_lines}

Write a concise coaching summary in Hebrew (3-4 paragraphs):
1. Overall performance verdict (profitable/unprofitable and by how much)
2. Behavioral patterns you notice (entry reasons, daily trend accuracy, mistakes)
3. What to improve next month — specific actionable advice
4. One encouraging sentence to end

Be honest, direct, and specific. Reference actual tickers and trades."""

    def _call():
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    return await asyncio.to_thread(_call)
