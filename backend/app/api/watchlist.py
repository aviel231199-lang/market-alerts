from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import User, WatchlistItem
from ..schemas import WatchIn, WatchOut
from ..security import current_user

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

_ALLOWED_KINDS = {"keyword", "ticker"}


@router.get("", response_model=list[WatchOut])
async def list_items(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> list[WatchlistItem]:
    rows = (await session.execute(select(WatchlistItem).where(WatchlistItem.user_id == user.id))).scalars().all()
    return list(rows)


@router.post("", response_model=WatchOut, status_code=status.HTTP_201_CREATED)
async def add_item(
    data: WatchIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> WatchlistItem:
    if data.kind not in _ALLOWED_KINDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "kind must be keyword|ticker")
    item = WatchlistItem(user_id=user.id, kind=data.kind, value=data.value.strip())
    session.add(item)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Already exists")
    await session.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await session.execute(
        delete(WatchlistItem).where(WatchlistItem.id == item_id, WatchlistItem.user_id == user.id)
    )
    await session.commit()
