from dotenv import load_dotenv

# Must run before any of the app.* imports below -- several of them
# (app.auth.security in particular) read environment variables at
# module-import time, so .env has to be loaded first or those reads
# silently fall back to their defaults instead.
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.incidents.router import router as incidents_router
from app.suppliers.router import router as suppliers_router
from app.auth.router import router as auth_router
from app.users.router import router as users_router
from app.profiles.router import router as profiles_router

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


@app.get("/")
async def root():
    return {"service": "nexova-api", "status": "ok"}
