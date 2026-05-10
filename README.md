# Market Alerts Platform

Real-time alerts for stock-market news (Bloomberg, WSJ, Investing, MarketWatch, CNBC, Yahoo Finance, Reuters, Seeking Alpha + Telegram channels), filtered by your personal watchlist of tickers and keywords, delivered as Push notifications to a Flutter mobile app.

## Architecture

```
[RSS feeds, Telegram] → collectors → Redis (dedup + pub/sub) → matcher → FCM → Mobile
                                       │
                                  PostgreSQL  ←→  FastAPI  ←→  Mobile
```

## Backend — Quick start

```bash
cd backend
cp .env.example .env   # fill JWT_SECRET, TELEGRAM_API_*, FCM_CREDENTIALS_FILE
docker compose up -d postgres redis
docker compose run --rm api alembic upgrade head
docker compose up api worker
```

Endpoints (JWT bearer):
- `POST /auth/register` `{email, password}` → `{access_token}`
- `POST /auth/login`
- `POST /devices` `{fcm_token, platform}`
- `GET/POST/DELETE /watchlist` (`kind`: `ticker` | `keyword`)
- `GET /news?since=ISO&limit=N`
- `GET/POST /sources/telegram`

## Mobile — Quick start

```bash
cd mobile
flutter pub get
# Place google-services.json (Android) / GoogleService-Info.plist (iOS)
flutter run --dart-define=API_BASE=http://10.0.2.2:8000
```

## Setup keys you must provide

| Variable | Where | Purpose |
|---|---|---|
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | https://my.telegram.org | Telethon login |
| `FCM_CREDENTIALS_FILE` | Firebase Console → Service Accounts | Push notifications |
| `JWT_SECRET` | random 32+ bytes | Auth |

## Files of note

- [backend/app/collectors/rss_collector.py](backend/app/collectors/rss_collector.py) — RSS poller with ETag/If-Modified-Since
- [backend/app/collectors/telegram_collector.py](backend/app/collectors/telegram_collector.py) — Telethon listener
- [backend/app/pipeline/store.py](backend/app/pipeline/store.py) — dedup + persist + publish
- [backend/app/matcher/engine.py](backend/app/matcher/engine.py) — watchlist matcher
- [backend/app/push/fcm.py](backend/app/push/fcm.py) — FCM sender
- [mobile/lib/main.dart](mobile/lib/main.dart) — Flutter entrypoint

## End-to-end verification

1. `docker compose up` — postgres + redis + api healthy
2. `curl -X POST localhost:8000/auth/register -d '{"email":"me@x.com","password":"pass1234"}' -H 'content-type: application/json'` → save token
3. Add ticker: `curl -X POST localhost:8000/watchlist -H "Authorization: Bearer $T" -H 'content-type: application/json' -d '{"kind":"ticker","value":"AAPL"}'`
4. Watch logs: `docker compose logs -f worker` — RSS items being ingested
5. Run Flutter app on emulator, log in, see news; trigger fresh AAPL story to confirm Push arrives within ~1 minute.

## Roadmap (not in v1)

- LLM-based Breaking/Routine classification
- Sentiment scoring
- X/Twitter integration
- iOS/Android home-screen widgets
