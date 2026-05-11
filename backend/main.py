"""SolSniper FastAPI entrypoint + WebSocket hub."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database.db import init_db
from backend.routers import proposals, portfolio, wallets


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    await init_db()
    yield


app = FastAPI(title="SolSniper API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(proposals.router, prefix="/proposals", tags=["proposals"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
app.include_router(wallets.router, prefix="/wallets", tags=["wallets"])


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "SolSniper", "week": 1}
