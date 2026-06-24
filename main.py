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

from db.client import db
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from zoneinfo import ZoneInfo
from jobs.unban_job import clear_expired_bans
from jobs.purge_soft_deleted_job import purge_soft_deleted_users
from jobs.daily_celebration_job import create_daily_celebration_posts
from jobs.leaderboard_digest_job import send_leaderboard_digest
from constants import APP_NAME, API_PREFIX
from routes import auth
from routes import users
from routes.app import auth as app_auth
from routes.app.posts import posts_router
from routes.alerts import alerts_router
from routes.app.users import app_users_router
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


app = FastAPI(title=APP_NAME, lifespan=lifespan)


# --- Static files ---
app.mount("/assets", StaticFiles(directory="public/assets"), name="assets")  # ← NEW


# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
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
# --- App Routes ---
app.include_router(app_auth.app_auth_router, prefix=API_PREFIX)
app.include_router(posts_router, prefix=API_PREFIX)
app.include_router(appreciation_types_router, prefix=API_PREFIX)
app.include_router(appreciations_router, prefix=API_PREFIX)
app.include_router(appreciation_types_app_router, prefix=API_PREFIX)
app.include_router(alerts_router, prefix=API_PREFIX)
app.include_router(app_users_router, prefix=API_PREFIX)
app.include_router(notifications_router, prefix=f"{API_PREFIX}/app")

# --- Health check ---
@app.get("/health")
async def health():
    return api_response(200, message="OK12")

from services.moderation_service import reload_static_filter, invalidate_blacklist_cache

@app.on_event("startup")
async def startup():
    await reload_static_filter()       # loads better-profanity with current whitelist
    await invalidate_blacklist_cache() # builds Aho-Corasick automata from DB
