"""Proposal endpoints (Week 3)."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_proposals():
    return {"proposals": []}


@router.post("/{proposal_id}/approve")
async def approve_proposal(proposal_id: int):
    return {"status": "not_implemented", "id": proposal_id}


@router.post("/{proposal_id}/reject")
async def reject_proposal(proposal_id: int):
    return {"status": "not_implemented", "id": proposal_id}
