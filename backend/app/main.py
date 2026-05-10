import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import auth, devices, news, sources, watchlist
from .config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = aioredis.from_url(settings.redis_url)
    try:
        yield
    finally:
        await app.state.redis.aclose()


app = FastAPI(title="Market Alerts API", lifespan=lifespan)

# CORS — tighten origins in production via env var ALLOWED_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # mobile apps don't use CORS; restrict if adding a web UI
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "PUT"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def _limit_body(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH"):
        cl = request.headers.get("content-length")
        if cl and int(cl) > settings.max_body_size:
            return JSONResponse(
                {"detail": "Request body too large"}, status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            )
    return await call_next(request)


app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(watchlist.router)
app.include_router(news.router)
app.include_router(sources.router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True}
