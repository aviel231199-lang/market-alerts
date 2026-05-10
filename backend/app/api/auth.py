import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import InviteCode, User
from ..schemas import LoginIn, TokenOut
from ..security import create_access_token, current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    invite_code: str = Field(min_length=4, max_length=64)


class CodeCreateIn(BaseModel):
    note: str | None = None
    count: int = Field(default=1, ge=1, le=50)


# ── Registration (invite-code gated) ──────────────────────────────────────

@router.post("/register", response_model=TokenOut)
async def register(data: RegisterIn, session: AsyncSession = Depends(get_session)) -> TokenOut:
    code_row = (
        await session.execute(
            select(InviteCode).where(
                InviteCode.code == data.invite_code.strip(),
                InviteCode.used.is_(False),
            )
        )
    ).scalar_one_or_none()

    if code_row is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid or already-used invite code")

    user = User(email=data.email.lower(), password_hash=hash_password(data.password))
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    code_row.used = True
    code_row.used_by_email = data.email.lower()
    code_row.used_at = datetime.now(timezone.utc)
    await session.commit()
    return TokenOut(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenOut)
async def login(data: LoginIn, session: AsyncSession = Depends(get_session)) -> TokenOut:
    user = (await session.execute(select(User).where(User.email == data.email.lower()))).scalar_one_or_none()
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return TokenOut(access_token=create_access_token(user.id))


# ── Admin helpers ──────────────────────────────────────────────────────────

def _require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user


@router.post("/codes/generate", tags=["admin"])
async def generate_codes(
    data: CodeCreateIn,
    _admin: User = Depends(_require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Generate invite codes. Admin only."""
    created = []
    for _ in range(data.count):
        code = secrets.token_urlsafe(8)  # ~11 chars, URL-safe
        session.add(InviteCode(code=code, note=data.note))
        created.append({"code": code, "note": data.note})
    await session.commit()
    return created


@router.get("/codes", tags=["admin"])
async def list_codes(
    _admin: User = Depends(_require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = (await session.execute(select(InviteCode).order_by(InviteCode.created_at.desc()))).scalars().all()
    return [
        {
            "id": r.id,
            "code": r.code,
            "note": r.note,
            "used": r.used,
            "used_by": r.used_by_email,
            "used_at": r.used_at.isoformat() if r.used_at else None,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.delete("/codes/{code_id}", tags=["admin"], status_code=status.HTTP_204_NO_CONTENT)
async def revoke_code(
    code_id: int,
    _admin: User = Depends(_require_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    row = (await session.execute(select(InviteCode).where(InviteCode.id == code_id))).scalar_one_or_none()
    if row:
        await session.delete(row)
        await session.commit()
