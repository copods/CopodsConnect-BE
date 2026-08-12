# main.py
from typing import override
from dotenv import load_dotenv
load_dotenv(override=True)  # must be first — loads .env before anything else reads os.getenv()

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles  # ← NEW
from prisma.errors import PrismaError
from fastapi import Request
import logging

from db.client import db
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from zoneinfo import ZoneInfo
from jobs.unban_job import clear_expired_bans
from jobs.purge_soft_deleted_job import purge_soft_deleted_users
from jobs.daily_celebration_job import create_daily_celebration_posts
from jobs.leaderboard_digest_job import send_leaderboard_digest
from constants import APP_NAME, API_PREFIX
from routes import auth
from routes.polls import panel_polls_router

from routes import users
from routes.app import auth as app_auth
from routes.app.posts import posts_router
from routes.alerts import alerts_router
from routes.app.users import app_users_router
from routes.stats import stats_router
from utils.exceptions import (
    AppException,
    app_exception_handler,
    validation_exception_handler,
    prisma_exception_handler,
    generic_exception_handler,
)
from utils.ApiResponse import api_response
from routes.appreciation_types import appreciation_types_router
from routes.app.appreciations import appreciations_router, appreciation_types_app_router
from routes.app.notifications import notifications_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(clear_expired_bans, "interval", minutes=15, id="clear_expired_bans")
    scheduler.add_job(purge_soft_deleted_users, "interval", days=1, id="purge_soft_deleted_users")
    scheduler.add_job(
        create_daily_celebration_posts,
        "cron",
        hour=0,
        minute=0,
        timezone=ZoneInfo("Asia/Kolkata"),
        id="daily_celebrations",
    )
    scheduler.add_job(
        send_leaderboard_digest,
        "cron",
        day_of_week="mon",
        hour=9,
        minute=0,
        timezone=ZoneInfo("Asia/Kolkata"),
        id="leaderboard_digest",
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)
    await db.disconnect()


app = FastAPI(title=APP_NAME, lifespan=lifespan, docs_url=None, redoc_url=None)

# We use the existing uvicorn logger so it prints perfectly to AWS CloudWatch
logger = logging.getLogger("uvicorn.error")
@app.middleware("http")
async def log_incoming_requests(request: Request, call_next):
    # 1. Capture the Host Header (handles ALB proxy forwarding)
    host_header = request.headers.get("x-forwarded-host") or request.headers.get("host", "Unknown Host")
    
    # 2. Capture the Hacker's Real IP (ALB passes it in x-forwarded-for)
    real_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "Unknown IP")
    
    # 3. Capture User-Agent
    user_agent = request.headers.get("user-agent", "Unknown Agent")
    
    # 4. Capture the exact URL path requested
    request_url = str(request.url)
    
    # Print a highly visible block in CloudWatch
    logger.info("\n=== [NETWORK LOG] NEW REQUEST ===")
    logger.info(f"Method & URL: {request.method} {request_url}")
    logger.info(f"Host Header : {host_header}")
    logger.info(f"Client IP   : {real_ip}")
    logger.info(f"User-Agent  : {user_agent}")
    
    # This single line is perfect for CloudWatch Insights searching:
    logger.info(f"SEARCH_STRING: METHOD={request.method} | IP={real_ip} | HOST={host_header} | URL={request_url}")
    logger.info("=================================\n")
    
    # Continue processing the request normally
    response = await call_next(request)
    return response

# --- Static files ---
app.mount("/assets", StaticFiles(directory="public/assets"), name="assets")  # ← NEW


def _parse_cors_origins(raw: str) -> list[str]:
    import json
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [o.strip() for o in parsed if o.strip()]
    except (json.JSONDecodeError, ValueError):
        pass
    return [o.strip() for o in raw.split(",") if o.strip()]

_CORS_ORIGINS = list({
    "http://localhost:5173",
    "https://dev.d1f79thuypnl1s.amplifyapp.com",
    *_parse_cors_origins(os.getenv("CORS_ORIGINS", "")),
})

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Exception handlers ---
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(PrismaError, prisma_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)



# --- Routes ---
app.include_router(auth.auth_router, prefix=API_PREFIX)
app.include_router(users.users_router, prefix=API_PREFIX)
app.include_router(panel_polls_router, prefix=API_PREFIX)
# --- App Routes ---
app.include_router(app_auth.app_auth_router, prefix=API_PREFIX)
app.include_router(posts_router, prefix=API_PREFIX)
app.include_router(appreciation_types_router, prefix=API_PREFIX)
app.include_router(appreciations_router, prefix=API_PREFIX)
app.include_router(appreciation_types_app_router, prefix=API_PREFIX)
app.include_router(alerts_router, prefix=API_PREFIX)
app.include_router(app_users_router, prefix=API_PREFIX)
app.include_router(notifications_router, prefix=f"{API_PREFIX}/app")
app.include_router(stats_router,prefix=API_PREFIX)
# --- Health check ---
@app.get("/health")
async def health():
    return api_response(200, message="OK12")

from services.moderation_service import reload_static_filter, invalidate_blacklist_cache

@app.on_event("startup")
async def startup():
    await reload_static_filter()       # loads better-profanity with current whitelist
    await invalidate_blacklist_cache() # builds Aho-Corasick automata from DB
