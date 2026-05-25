# main.py
from dotenv import load_dotenv
load_dotenv()  # must be first — loads .env before anything else reads os.getenv()

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from prisma.errors import PrismaError

from db.client import db
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from jobs.unban_job import clear_expired_bans
from jobs.purge_soft_deleted_job import purge_soft_deleted_users
from constants import APP_NAME, API_PREFIX
from routes import auth
from routes import users
from utils.exceptions import (
    AppException,
    app_exception_handler,
    validation_exception_handler,
    prisma_exception_handler,
    generic_exception_handler,
)
from utils.ApiResponse import api_response


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(clear_expired_bans, "interval", minutes=15, id="clear_expired_bans")
    scheduler.add_job(purge_soft_deleted_users, "interval", days=1, id="purge_soft_deleted_users")
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)
    await db.disconnect()


app = FastAPI(title=APP_NAME, lifespan=lifespan)


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

# --- Health check ---
@app.get("/health")
async def health():
    return api_response(200, message="OK12")