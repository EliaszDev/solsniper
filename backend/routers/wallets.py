"""Wallet watchlist endpoints (Week 2+)."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_wallets():
    return {"wallets": []}


@router.post("/")
async def add_wallet():
    return {"status": "not_implemented"}


@router.delete("/{address}")
async def remove_wallet(address: str):
    return {"status": "not_implemented", "address": address}
