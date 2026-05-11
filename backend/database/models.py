"""SQLAlchemy ORM models."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.database.db import Base


class Proposal(Base):
    __tablename__ = "proposals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String, nullable=False)          # 'whale_copy' | 'snipe'
    token_mint = Column(String, nullable=False)
    token_symbol = Column(String, nullable=False)
    source_wallet = Column(String, nullable=True)  # whale wallet (whale_copy only)
    suggested_size = Column(Float, default=0.0)    # USD
    take_profit = Column(Text, default="[]")       # JSON array of % levels
    stop_loss = Column(Float, default=0.0)         # %
    confidence = Column(Integer, default=0)        # 0-100
    reasoning = Column(Text, default="")
    status = Column(String, default="pending")     # 'pending' | 'approved' | 'rejected' | 'executed' | 'expired'
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    tx_signature = Column(String, nullable=True)

    position = relationship("Position", back_populates="proposal", uselist=False)


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    proposal_id = Column(Integer, ForeignKey("proposals.id"), nullable=True)
    token_mint = Column(String, nullable=False)
    token_symbol = Column(String, nullable=False)
    entry_price_sol = Column(Float, default=0.0)
    entry_size_usd = Column(Float, default=0.0)
    entry_tx = Column(String, nullable=True)
    current_price = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, default=0.0)
    status = Column(String, default="open")        # 'open' | 'closed'
    exit_price_sol = Column(Float, nullable=True)
    realized_pnl = Column(Float, default=0.0)
    exit_tx = Column(String, nullable=True)
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    proposal = relationship("Proposal", back_populates="position")


class WatchedWallet(Base):
    __tablename__ = "watched_wallets"

    address = Column(String, primary_key=True)
    label = Column(String, nullable=True)
    score = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    avg_pnl_sol = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    last_seen = Column(DateTime, nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow)
