from datetime import datetime
from decimal import Decimal

from sqlalchemy import ARRAY, BigInteger, Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)  # Bloomberg/paid sources
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    devices: Mapped[list["Device"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    watchlist: Mapped[list["WatchlistItem"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    trades: Mapped[list["Trade"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    telegram_sources: Mapped[list["UserTelegramSource"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    fcm_token: Mapped[str] = mapped_column(String(512), unique=True)
    platform: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="devices")


class WatchlistItem(Base):
    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("user_id", "kind", "value", name="uq_watch_user_kind_value"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # keyword | ticker
    value: Mapped[str] = mapped_column(String(128))

    user: Mapped[User] = relationship(back_populates="watchlist")


class Trade(Base):
    """Trading journal entry."""
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    ticker: Mapped[str] = mapped_column(String(16), index=True)
    direction: Mapped[str] = mapped_column(String(8))          # long | short
    market: Mapped[str] = mapped_column(String(32), default="stock")  # stock | option | crypto | forex

    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    take_profit: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)

    entry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    exit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    daily_trend: Mapped[str | None] = mapped_column(String(8), nullable=True)   # bullish | bearish | neutral
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)              # why I entered
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)               # post-trade notes
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)     # e.g. ["breakout","news"]

    status: Mapped[str] = mapped_column(String(16), default="open")  # open | closed | cancelled

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="trades")

    @property
    def pnl(self) -> Decimal | None:
        if self.exit_price is None:
            return None
        diff = self.exit_price - self.entry_price
        if self.direction == "short":
            diff = -diff
        return diff * self.quantity

    @property
    def pnl_pct(self) -> float | None:
        if self.exit_price is None or self.entry_price == 0:
            return None
        diff = float(self.exit_price - self.entry_price) / float(self.entry_price) * 100
        return diff if self.direction == "long" else -diff


class UserTelegramSource(Base):
    """Per-user Telegram channel subscriptions (private groups allowed)."""
    __tablename__ = "user_telegram_sources"
    __table_args__ = (UniqueConstraint("user_id", "channel", name="uq_user_tg_channel"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(255))
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped[User] = relationship(back_populates="telegram_sources")


class NewsItem(Base):
    __tablename__ = "news"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text)
    tickers: Mapped[list[str]] = mapped_column(ARRAY(String(16)), default=list)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)  # Bloomberg/paid
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TelegramSource(Base):
    """Global/shared Telegram channels (admin-managed)."""
    __tablename__ = "telegram_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[str] = mapped_column(String(255), unique=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(default=True)
