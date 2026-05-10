"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "devices",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("fcm_token", sa.String(512), nullable=False, unique=True),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "watchlist",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("value", sa.String(128), nullable=False),
        sa.UniqueConstraint("user_id", "kind", "value", name="uq_watch_user_kind_value"),
    )

    op.create_table(
        "news",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("source", sa.String(64), nullable=False, index=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("tickers", sa.ARRAY(sa.String(16)), server_default="{}"),
        sa.Column("published_at", sa.DateTime(timezone=True), index=True),
        sa.Column("hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "telegram_sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("channel", sa.String(255), nullable=False, unique=True),
        sa.Column("label", sa.String(255)),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    for t in ("telegram_sources", "news", "watchlist", "devices", "users"):
        op.drop_table(t)
