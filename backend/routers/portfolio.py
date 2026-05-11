"""Portfolio endpoints (Week 3)."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/positions")
async def list_positions():
    return {"positions": []}


@router.get("/history")
async def trade_history():
    return {"history": []}
