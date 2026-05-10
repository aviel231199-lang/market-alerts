"""Background workers entrypoint: runs RSS, Telegram, Matcher, and FCM workers concurrently."""

import asyncio
import logging

import redis.asyncio as aioredis

from .collectors import finnhub_collector, rss_collector, telegram_collector
from .config import settings
from .matcher import engine as matcher_engine
from .push import fcm

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


async def main() -> None:
    redis = aioredis.from_url(settings.redis_url)
    log.info("starting workers")
    tasks = [
        asyncio.create_task(rss_collector.run(redis), name="rss"),
        asyncio.create_task(telegram_collector.run(redis), name="telegram"),
        asyncio.create_task(matcher_engine.run(redis), name="matcher"),
        asyncio.create_task(fcm.run(redis), name="fcm"),
        asyncio.create_task(finnhub_collector.run(redis), name="finnhub"),
    ]
    try:
        await asyncio.gather(*tasks)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
