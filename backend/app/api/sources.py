from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import TelegramSource, User
from ..schemas import TelegramSourceIn
from ..security import current_user

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("/telegram")
async def list_telegram(
    _: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = (await session.execute(select(TelegramSource))).scalars().all()
    return [{"id": r.id, "channel": r.channel, "label": r.label, "active": r.active} for r in rows]


@router.post("/telegram", status_code=status.HTTP_201_CREATED)
async def add_telegram(
    data: TelegramSourceIn,
    _: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = (
        pg_insert(TelegramSource)
        .values(channel=data.channel, label=data.label, active=True)
        .on_conflict_do_update(index_elements=["channel"], set_={"label": data.label, "active": True})
        .returning(TelegramSource.id)
    )
    res = await session.execute(stmt)
    await session.commit()
    return {"id": res.scalar_one(), "channel": data.channel}
