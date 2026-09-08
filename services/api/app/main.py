from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.incidents.router import router as incidents_router
from app.suppliers.router import router as suppliers_router
app = FastAPI(title="Nexova API", version="0.1.0")

# Allow the independently-deployed Nexova frontends to call this API.
# See docs/ARCHITECTURE_PROPOSAL.md section 5: explicit origins, not a
# wildcard, since this API handles sensitive incident/customer data.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(incidents_router)
app.include_router(suppliers_router)

@app.get("/")
async def root():
    return {"service": "nexova-api", "status": "ok"}
