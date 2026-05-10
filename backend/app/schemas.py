from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


_ALLOWED_PLATFORMS = {"ios", "android"}


class DeviceIn(BaseModel):
    fcm_token: str = Field(min_length=10, max_length=512)
    platform: str = Field(pattern="^(ios|android)$")


class WatchIn(BaseModel):
    kind: str = Field(pattern="^(keyword|ticker)$")
    value: str = Field(min_length=1, max_length=128)


class WatchOut(WatchIn):
    id: int


class NewsOut(BaseModel):
    id: int
    source: str
    title: str
    summary: str | None
    url: str
    tickers: list[str]
    published_at: datetime

    class Config:
        from_attributes = True


class TelegramSourceIn(BaseModel):
    channel: str
    label: str | None = None
