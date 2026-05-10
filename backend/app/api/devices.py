from fastapi import APIRouter, Depends, status
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Device, User
from ..schemas import DeviceIn
from ..security import current_user

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def register_device(
    data: DeviceIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    stmt = (
        pg_insert(Device)
        .values(user_id=user.id, fcm_token=data.fcm_token, platform=data.platform)
        .on_conflict_do_update(index_elements=["fcm_token"], set_={"user_id": user.id, "platform": data.platform})
    )
    await session.execute(stmt)
    await session.commit()
