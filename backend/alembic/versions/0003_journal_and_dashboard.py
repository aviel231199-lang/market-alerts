"""trades, user_telegram_sources, user premium, news is_premium

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_premium", sa.Boolean, nullable=False, server_default=sa.false()))
    op.add_column("news", sa.Column("is_premium", sa.Boolean, nullable=False, server_default=sa.false()))

    op.create_table(
        "trades",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("ticker", sa.String(16), nullable=False, index=True),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("market", sa.String(32), nullable=False, server_default="stock"),
        sa.Column("entry_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("exit_price", sa.Numeric(18, 6)),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("stop_loss", sa.Numeric(18, 6)),
        sa.Column("take_profit", sa.Numeric(18, 6)),
        sa.Column("entry_at", sa.DateTime(timezone=True), index=True),
        sa.Column("exit_at", sa.DateTime(timezone=True)),
        sa.Column("daily_trend", sa.String(8)),
        sa.Column("reason", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("tags", sa.ARRAY(sa.String(32)), server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "user_telegram_sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("channel", sa.String(255), nullable=False),
        sa.Column("label", sa.String(255)),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("user_id", "channel", name="uq_user_tg_channel"),
    )


def downgrade() -> None:
    op.drop_table("user_telegram_sources")
    op.drop_table("trades")
    op.drop_column("news", "is_premium")
    op.drop_column("users", "is_premium")
