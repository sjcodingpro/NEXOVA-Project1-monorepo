import logging
import uuid

from dotenv import load_dotenv

# Must run before any of the app.* imports below -- several of them
# (app.auth.security in particular) read environment variables at
# module-import time, so .env has to be loaded first or those reads
# silently fall back to their defaults instead.
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import check_db_readable
from app.incidents.router import router as incidents_router
from app.suppliers.router import router as suppliers_router
from app.auth.router import router as auth_router
from app.users.router import router as users_router
from app.profiles.router import router as profiles_router

logger = logging.getLogger("nexova_api")

app = FastAPI(title="Nexova API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(incidents_router)
app.include_router(suppliers_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(profiles_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # A route with no error handling of its own would otherwise let a raw
    # traceback (with local file paths, variable values, etc.) reach the
    # client as the FastAPI/Starlette default 500 body. This catches
    # anything not already handled, logs the real exception with a
    # correlation id server-side only, and returns a generic body.
    error_id = str(uuid.uuid4())
    logger.exception("Unhandled exception [%s] on %s %s", error_id, request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred.", "error_id": error_id},
    )


@app.get("/")
async def root():
    return {"service": "nexova-api", "status": "ok"}


@app.get("/health")
async def health():
    db_ok = check_db_readable()
    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={
            "service": "nexova-api",
            "status": "ok" if db_ok else "degraded",
            "db": "ok" if db_ok else "unreachable",
        },
    )
