"""Wallet watchlist endpoints (Week 2+)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from solders.pubkey import Pubkey

router = APIRouter()


def _validate_address(addr: str) -> str:
    """Validate a Solana base-58 address."""
    if not addr or len(addr) > 44:
        raise HTTPException(status_code=400, detail="Invalid address length")
    try:
        Pubkey.from_string(addr)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base58 address: {exc}") from exc
    return addr


class WalletAdd(BaseModel):
    address: str = Field(..., description="Base58 Solana wallet address")
    label: str | None = Field(default=None, description="Optional label")


@router.get("/")
async def list_wallets():
    return {"wallets": []}


@router.post("/")
async def add_wallet(body: WalletAdd):
    _validate_address(body.address)
    return {"status": "not_implemented", "address": body.address, "label": body.label}


@router.delete("/{address}")
async def remove_wallet(address: str):
    _validate_address(address)
    return {"status": "not_implemented", "address": address}
