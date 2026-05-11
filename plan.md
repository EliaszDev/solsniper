# SolSniper — Detailed Project Plan
**Nanobot-Powered Solana Trading Agent | Kimi K2 via API | Personal Use**

---

## Overview

SolSniper is a semi-autonomous Solana trading tool built on top of the `nanobot` multi-agent framework, powered by Kimi K2 as the LLM backend. It runs two parallel agent modules — a **Whale Tracker** that copies high-profit wallets, and a **Token Sniper** that identifies and scores new token launches — both feeding into a React UI where you approve or reject trades before execution via Jupiter Swap API.

The system runs entirely on your local VM. Pure alpha.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent framework | `nanobot` (already running on VM) |
| LLM | Kimi K2 via API (already configured) |
| Whale data | Helius Wallet API (free, 1M credits/month) |
| New token launches | PumpDev WebSocket (`wss://pumpdev.io/ws`) |
| Token pair data + scoring | DexScreener REST API (free, no key) |
| Safety / red flags | RugCheck.xyz API + Solscan API |
| Swap execution | Jupiter Swap API (free) |
| Backend | FastAPI + WebSockets |
| Database | SQLite (via SQLAlchemy) |
| Frontend | React + Tailwind CSS + Recharts |
| Runtime | Python 3.11+, Node 20+ |

---

## Repository Structure

```
solsniper/
├── backend/
│   ├── main.py                  # FastAPI entrypoint, WebSocket hub
│   ├── config.py                # API keys, wallet list, thresholds
│   ├── database/
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   └── db.py                # SQLite engine + session
│   ├── agents/
│   │   ├── base_agent.py        # Shared nanobot agent config (Kimi K2 endpoint)
│   │   ├── whale_agent.py       # Whale Tracker Agent
│   │   └── sniper_agent.py      # Token Sniper Agent
│   ├── services/
│   │   ├── helius.py            # Helius API client
│   │   ├── dexscreener.py       # DexScreener REST client
│   │   ├── pumpdev_ws.py        # PumpDev WebSocket listener
│   │   ├── rugcheck.py          # RugCheck.xyz + Solscan safety checks
│   │   └── jupiter.py           # Jupiter quote + swap execution
│   ├── scoring/
│   │   ├── whale_scorer.py      # P&L, win rate, recency scoring logic
│   │   └── launch_scorer.py     # Token launch scoring logic
│   ├── routers/
│   │   ├── proposals.py         # GET/POST proposal endpoints
│   │   ├── portfolio.py         # Open positions, P&L, trade history
│   │   ├── wallets.py           # Watchlist CRUD
│   │   └── ws.py                # WebSocket endpoint for live feed
│   └── tasks/
│       ├── whale_poll.py        # Background polling task (asyncio)
│       └── sniper_poll.py       # Background PumpDev listener task
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Feed.jsx         # Live opportunity feed
│   │   │   ├── ProposalCard.jsx # Approve/Reject card UI
│   │   │   ├── Portfolio.jsx    # Open positions + P&L
│   │   │   ├── WalletManager.jsx# Whale watchlist manager
│   │   │   └── Charts.jsx       # Token price charts (Recharts)
│   │   ├── hooks/
│   │   │   └── useWebSocket.js  # WS connection hook
│   │   ├── api/
│   │   │   └── client.js        # Axios client to FastAPI
│   │   └── App.jsx
│   └── package.json
├── .env                         # API keys (never committed)
├── requirements.txt
└── README.md
```

---

## Module 1 — Whale Tracker Agent

### Purpose
Monitor a user-defined list of high-profit Solana wallets. When a tracked whale executes a swap, score it and propose a copy trade to the user.

### Data Source: Helius Wallet API

**Endpoint:** `GET https://api.helius.xyz/v1/wallet/{address}/history?api-key={KEY}&type=SWAP`

**What it returns per swap:**
- `timestamp` — Unix timestamp of the transaction
- `tokenTransfers` — array of token movements (in/out)
- `balanceChanges` — SOL delta
- `nativeTransfers` — raw SOL transfers
- Swap direction inferrable from `balanceChanges`: negative SOL = buy, positive SOL = sell

**Polling strategy:**
- Poll each tracked wallet every 30 seconds using `asyncio` background tasks
- Store last-seen transaction signature per wallet to avoid duplicate processing
- With 20 wallets × 2 req/min = 2,400 req/hour → well within 1M monthly credits

### Wallet Scoring Engine (`whale_scorer.py`)

For each tracked wallet, maintain a live score in SQLite computed from:

| Metric | Formula | Weight |
|---|---|---|
| Win rate | `profitable_closed_trades / total_closed_trades` | 40% |
| Avg realized P&L | Mean of `(sell_value_SOL - buy_value_SOL)` per closed position | 30% |
| Recency | Exponential decay on last swap timestamp | 20% |
| Trade frequency | Trades per 7-day window (prefers active wallets) | 10% |

**Position tracking logic:**
- On SWAP IN (buy): open a position record `{wallet, token_mint, buy_price_sol, buy_amount, timestamp}`
- On SWAP OUT (sell): match to open position, compute realized P&L, close position
- Unmatched sells (whale sold before we started tracking): discard

**Wallet score updated** every time a new swap is processed.

### Whale Agent (`whale_agent.py`) — Kimi K2 via nanobot

When a tracked whale executes a buy swap, the agent receives:

```
Context:
- Token mint: {mint}
- Token symbol: {symbol} (from DexScreener)
- Whale wallet score: {score}/100
- Whale historical win rate: {win_rate}%
- Current token liquidity: ${liquidity}
- 1h price change: {price_change_1h}%
- RugCheck safety: {safe/flagged}
- Top 10 holder concentration: {concentration}%

Task: Should I copy this trade? Propose entry size (max $50), take-profit target (%), stop-loss (%). Explain in 2 sentences.
```

**Agent output (structured JSON):**
```json
{
  "recommendation": "BUY",
  "confidence": 78,
  "suggested_size_usd": 30,
  "take_profit_pct": 120,
  "stop_loss_pct": 40,
  "reasoning": "High-conviction whale with 73% win rate bought into a token with growing liquidity and no rug flags. Suggesting conservative $30 entry with 2x TP target."
}
```

This becomes a **Proposal** stored in SQLite and pushed to the UI via WebSocket.

---

## Module 2 — Token Sniper Agent

### Purpose
Detect new Solana token launches in real time, score them for alpha potential and safety, and propose snipe entries before momentum peaks.

### Data Source 1: PumpDev WebSocket

**Endpoint:** `wss://pumpdev.io/ws`

**Subscribe message:**
```json
{"method": "subscribeNewToken"}
```

**Event payload per new token:**
```json
{
  "mint": "...",
  "name": "TokenName",
  "symbol": "TKN",
  "creator": "wallet_address",
  "initialBuy": 0.5,
  "marketCapSol": 30,
  "uri": "metadata_uri"
}
```

**Handled in:** `pumpdev_ws.py` — persistent async WebSocket connection with auto-reconnect on disconnect.

### Data Source 2: DexScreener REST API

After receiving a new token event from PumpDev, immediately query:

`GET https://api.dexscreener.com/latest/dex/tokens/{mint}`

**Extracted fields:**
- `volume.h1` — 1-hour volume in USD
- `txns.h1.buys` / `txns.h1.sells` — buy/sell transaction counts
- `liquidity.usd` — current liquidity
- `priceChange.h1` — 1h price change %
- `pairCreatedAt` — age of the pair in seconds

### Token Launch Scoring Engine (`launch_scorer.py`)

Score each new token 0–100 before passing to Kimi K2:

| Signal | Condition | Score Contribution |
|---|---|---|
| Volume velocity | `volume.h1 > $5,000` in first 10 min | +25 |
| Buy pressure | `buy_txns / (buy_txns + sell_txns) > 0.65` | +20 |
| Liquidity depth | `liquidity.usd > $10,000` | +15 |
| Age | Token < 5 minutes old | +15 |
| RugCheck safe | No mint/freeze authority, locked liquidity | +15 |
| Holder concentration | Top 10 holders < 40% of supply | +10 |

Tokens scoring **< 50** are silently discarded. Tokens **≥ 50** are passed to the Sniper Agent.

### Safety Checks (`rugcheck.py`)

For every token that passes the numeric score threshold:

**RugCheck.xyz API:** `GET https://api.rugcheck.xyz/v1/tokens/{mint}/report`
- Check: `mintAuthorityEnabled` → if `true`, flag as HIGH RISK
- Check: `freezeAuthorityEnabled` → if `true`, flag as HIGH RISK
- Check: `lpLocked` → if `false`, flag as MEDIUM RISK

**Solscan API:** `GET https://public-api.solscan.io/token/holders?tokenAddress={mint}&limit=10`
- Compute top-10 holder concentration: `sum(top10_balances) / total_supply * 100`
- If > 50%: flag as HIGH RISK

Any HIGH RISK flag → token discarded immediately, no proposal generated.

### Sniper Agent (`sniper_agent.py`) — Kimi K2 via nanobot

For tokens passing numeric score + safety checks:

```
Context:
- Token: {name} ({symbol})
- Mint: {mint}
- Age: {age} seconds
- Launch score: {score}/100
- 1h Volume: ${volume_1h}
- Buy pressure: {buy_pct}% buys
- Liquidity: ${liquidity}
- Safety: CLEAN (no flags)
- Holder concentration: {concentration}%
- Creator wallet: {creator} (new wallet: yes/no)

Task: Is this worth sniping? If yes, suggest entry size (max $50), take-profit targets (multiple levels), stop-loss. Explain briefly.
```

**Agent output:**
```json
{
  "recommendation": "SNIPE",
  "confidence": 65,
  "suggested_size_usd": 20,
  "take_profit_levels": [150, 300, 500],
  "stop_loss_pct": 50,
  "reasoning": "Strong early buy pressure with clean contract and growing liquidity. Small position justified; high risk/reward with layered TP targets."
}
```

---

## Proposal System

### SQLite Schema

**Table: `proposals`**
```sql
id               INTEGER PRIMARY KEY
type             TEXT        -- 'whale_copy' | 'snipe'
token_mint       TEXT
token_symbol     TEXT
source_wallet    TEXT        -- whale wallet (whale_copy only)
suggested_size   REAL        -- USD
take_profit      TEXT        -- JSON array of % levels
stop_loss        REAL        -- %
confidence       INTEGER     -- 0-100
reasoning        TEXT
status           TEXT        -- 'pending' | 'approved' | 'rejected' | 'executed' | 'expired'
created_at       DATETIME
approved_at      DATETIME
executed_at      DATETIME
tx_signature     TEXT        -- Solana tx hash after execution
```

**Table: `positions`**
```sql
id               INTEGER PRIMARY KEY
proposal_id      INTEGER     -- FK to proposals
token_mint       TEXT
token_symbol     TEXT
entry_price_sol  REAL
entry_size_usd   REAL
entry_tx         TEXT
current_price    REAL        -- updated periodically
unrealized_pnl   REAL
status           TEXT        -- 'open' | 'closed'
exit_price_sol   REAL
realized_pnl     REAL
exit_tx          TEXT
opened_at        DATETIME
closed_at        DATETIME
```

**Table: `watched_wallets`**
```sql
address          TEXT PRIMARY KEY
label            TEXT        -- user-set nickname
score            REAL
win_rate         REAL
avg_pnl_sol      REAL
total_trades     INTEGER
last_seen        DATETIME
added_at         DATETIME
```

### Proposal Lifecycle

```
Agent generates proposal
        ↓
Stored in SQLite (status: pending)
        ↓
Pushed to UI via WebSocket
        ↓
User sees Proposal Card in UI
        ↓
    ┌───┴───┐
 Approve   Reject
    ↓         ↓
Jupiter   status: rejected
gets quote
    ↓
Execute swap
    ↓
status: executed
tx_signature stored
position opened
```

**Proposals expire** after 3 minutes if not actioned (configurable). Stale proposals are auto-rejected.

---

## Execution Layer (`jupiter.py`)

### Quote

`GET https://quote-api.jup.ag/v6/quote`
```
inputMint=So11111111111111111111111111111111111111112  (SOL)
outputMint={token_mint}
amount={lamports}  # convert from USD → SOL → lamports
slippageBps=300    # 3% slippage default, configurable
```

### Swap

`POST https://quote-api.jup.ag/v6/swap`
```json
{
  "quoteResponse": {...},
  "userPublicKey": "{your_wallet_pubkey}",
  "wrapAndUnwrapSol": true
}
```
Returns a base64-encoded transaction.

### Sign & Send

- Deserialize the transaction
- Sign with your wallet keypair (loaded from `.env`, never hardcoded)
- Submit via Helius RPC (faster finality than public RPC): `POST https://mainnet.helius-rpc.com/?api-key={KEY}`
- Poll for confirmation, store tx signature

**Wallet keypair** stored in `.env` as `WALLET_PRIVATE_KEY` (base58). Loaded once at startup, never logged.

---

## FastAPI Backend

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/proposals` | List pending proposals |
| `POST` | `/proposals/{id}/approve` | Approve → trigger Jupiter execution |
| `POST` | `/proposals/{id}/reject` | Reject proposal |
| `GET` | `/portfolio/positions` | Open positions with live P&L |
| `GET` | `/portfolio/history` | Closed trades + realized P&L |
| `GET` | `/wallets` | Get watchlist |
| `POST` | `/wallets` | Add wallet to watchlist |
| `DELETE` | `/wallets/{address}` | Remove wallet |
| `WS` | `/ws/feed` | Live stream: new proposals + position updates |

### WebSocket Feed Events

```json
{ "type": "new_proposal", "data": { ...proposal } }
{ "type": "proposal_expired", "data": { "id": 42 } }
{ "type": "position_update", "data": { "id": 7, "unrealized_pnl": 12.4 } }
{ "type": "trade_executed", "data": { ...position } }
```

### Background Tasks (asyncio)

- `whale_poll_task` — runs every 30s, polls Helius for all watched wallets
- `pumpdev_listener_task` — persistent WS connection to PumpDev, auto-reconnects
- `position_updater_task` — runs every 60s, fetches current prices for open positions via DexScreener, updates unrealized P&L
- `proposal_expiry_task` — runs every 30s, marks pending proposals older than 3 min as expired

---

## React Frontend

### Pages / Views

**1. Live Feed (main view)**
- Split into two columns: Whale Copies | New Snipes
- Each new event animates in from top
- Proposal cards show: token name/symbol, type badge, confidence bar, suggested size, reasoning snippet, TP/SL levels, countdown timer (expires in Xs)
- **Approve** (green) / **Reject** (red) buttons — single click, immediate API call
- After approval: card shows "Executing…" spinner → "✓ Executed" with tx link

**2. Portfolio**
- Table of open positions: token, entry price, current price, size, unrealized P&L (green/red), age
- "Close" button per position (triggers Jupiter sell)
- Realized P&L summary: total profit, win rate, best trade, worst trade
- Simple equity curve chart (Recharts LineChart)

**3. Whale Watchlist**
- Table: wallet address (truncated), label, score, win rate, avg P&L, last active
- Add wallet form: paste address + optional label
- Remove button per row
- Click wallet → see its recent swap history in a side panel

**4. Settings**
- Max position size (USD) — default $50
- Slippage tolerance (bps)
- Minimum launch score threshold
- Proposal expiry time (seconds)
- Helius API key input
- Wallet address display (read-only)

### WebSocket Hook (`useWebSocket.js`)

Persistent connection to `/ws/feed`. On message:
- `new_proposal` → prepend to feed, play subtle audio ping
- `proposal_expired` → remove card or mark grey
- `position_update` → update P&L in portfolio table in real time
- `trade_executed` → toast notification with tx link

---

## Configuration (`.env`)

```
HELIUS_API_KEY=your_helius_key
WALLET_PRIVATE_KEY=your_base58_keypair
KIMI_API_KEY=your_kimi_key
KIMI_API_BASE=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k2
MAX_POSITION_SIZE_USD=50
MIN_SNIPE_SCORE=50
PROPOSAL_EXPIRY_SECONDS=180
SLIPPAGE_BPS=300
```

---

## 6-Week Build Plan

### Week 1 — Data Foundation
- Set up repo structure, FastAPI skeleton, SQLite schema
- Implement `helius.py`: wallet history polling, swap parsing
- Implement `pumpdev_ws.py`: WebSocket listener, auto-reconnect
- Implement `dexscreener.py`: token pair data fetcher
- Test: manually query 3 known whale wallets, log raw events

### Week 2 — Scoring + Agents
- Build `whale_scorer.py`: P&L tracking, position matching, win rate calc
- Build `launch_scorer.py`: numeric scoring pipeline
- Build `rugcheck.py`: RugCheck + Solscan safety checks
- Integrate nanobot with Kimi K2: configure `base_agent.py`
- Build `whale_agent.py` and `sniper_agent.py` with prompts
- Test: feed mock swap data → verify agent proposals are sane

### Week 3 — Execution + Backend
- Build `jupiter.py`: quote, swap, sign, submit, confirm
- Wire proposal approval flow: approve endpoint → Jupiter → store tx
- Build all FastAPI routers
- Build background asyncio tasks
- Build WebSocket hub
- Test: paper trade 5 real proposals end-to-end (without real money)

### Week 4 — React Frontend
- Scaffold React app with Tailwind
- Build `Feed.jsx` + `ProposalCard.jsx` with approve/reject
- Build WebSocket hook, connect to backend
- Build `Portfolio.jsx` with live P&L updates
- Build `WalletManager.jsx`

### Week 5 — Polish + Real Testing
- Build `Charts.jsx` (equity curve, token price sparklines)
- Build Settings page
- Add toast notifications, audio ping on new proposals
- Switch from paper to real execution mode
- Run live for 3–5 days with small sizes ($5–$10), monitor behavior

### Week 6 — Tuning
- Adjust scoring thresholds based on observed proposal quality
- Tune Kimi K2 prompts: reduce false positives, improve TP/SL calibration
- Add simple backtesting script: replay historical DexScreener data through scorer
- Write README with setup guide
- Record short demo video for portfolio

---

## Risk Notes

- **Never commit `.env` to git.** Add to `.gitignore` immediately.
- Start with `MAX_POSITION_SIZE_USD=10` for the first week of live trading.
- New token sniping is high risk — most launches fail. Treat snipe proposals as lottery tickets.
- Whale copy-trading has inherent lag (30s poll + agent processing). Works better for mid-cap tokens than micro-caps with instant dumps.
- Jupiter slippage of 3% is a starting point — may need to increase for low-liquidity tokens.
