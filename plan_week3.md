# Week 3 — Execution + Backend: Granular Build Plan
**Each step is a single, focused task for the nanobot agent. Complete and test each before moving to the next.**

---

## Step 1 — `jupiter.py`: Get a Quote

**Goal:** Given a token mint and a USD amount, return a Jupiter swap quote.

**What to build:**
- Function `get_quote(token_mint: str, amount_usd: float) -> dict`
- Convert `amount_usd` → SOL using a live SOL/USD price (fetch from DexScreener: `GET https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112`)
- Convert SOL → lamports (`lamports = sol * 1_000_000_000`)
- Call Jupiter quote API:
  ```
  GET https://quote-api.jup.ag/v6/quote
    ?inputMint=So11111111111111111111111111111111111111112
    &outputMint={token_mint}
    &amount={lamports}
    &slippageBps={SLIPPAGE_BPS from config}
  ```
- Return raw quote response dict (store for use in Step 2)

**Test:** Call `get_quote("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", 10.0)` (USDC mint as dummy), print quote. Confirm `outAmount` field is present.

---

## Step 2 — `jupiter.py`: Build the Swap Transaction

**Goal:** Turn a quote into a base64-encoded, ready-to-sign transaction.

**What to build:**
- Function `build_swap_tx(quote: dict, wallet_pubkey: str) -> str` (returns base64 tx)
- Call Jupiter swap API:
  ```
  POST https://quote-api.jup.ag/v6/swap
  Body: {
    "quoteResponse": {quote},
    "userPublicKey": "{wallet_pubkey}",
    "wrapAndUnwrapSol": true,
    "dynamicComputeUnitLimit": true,
    "prioritizationFeeLamports": 1000
  }
  ```
- Extract `swapTransaction` field from response (this is the base64 tx)
- Return it as a string

**Test:** Chain with Step 1 — get a quote, build the tx, print the first 60 chars of the base64 string. Confirm it's non-empty and starts with a valid base64 prefix.

---

## Step 3 — `jupiter.py`: Sign the Transaction

**Goal:** Load wallet keypair from `.env` and sign the base64 transaction.

**What to build:**
- Function `sign_tx(base64_tx: str) -> bytes` (returns signed tx bytes)
- Load `WALLET_PRIVATE_KEY` from env (base58 string)
- Decode base64 tx → raw bytes
- Deserialize as a Solana `VersionedTransaction` using `solders` library
  ```python
  from solders.transaction import VersionedTransaction
  from solders.keypair import Keypair
  import base64, base58
  
  keypair = Keypair.from_base58_string(os.getenv("WALLET_PRIVATE_KEY"))
  raw = base64.b64decode(base64_tx)
  tx = VersionedTransaction.from_bytes(raw)
  tx.sign([keypair])
  signed_bytes = bytes(tx)
  ```
- Return signed bytes

**Test:** Use a dummy/test wallet keypair (not your real one). Sign the tx from Step 2, confirm no exception is raised and signed_bytes is non-empty.

---

## Step 4 — `jupiter.py`: Submit + Confirm Transaction

**Goal:** Send the signed transaction to the Solana network via Helius RPC and wait for confirmation.

**What to build:**
- Function `submit_tx(signed_bytes: bytes) -> str` (returns tx signature string)
- Encode signed bytes back to base64
- Send via Helius RPC:
  ```
  POST https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}
  Body: {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "sendTransaction",
    "params": [
      "{base64_signed_tx}",
      {"encoding": "base64", "maxRetries": 3, "skipPreflight": false}
    ]
  }
  ```
- Extract `result` field → this is the tx signature
- Function `confirm_tx(signature: str, timeout_seconds: int = 30) -> bool`
  - Poll `getSignatureStatuses` RPC method every 2 seconds
  - Return `True` when `confirmationStatus` is `"confirmed"` or `"finalized"`
  - Return `False` on timeout

**Test (paper mode — DO NOT run against mainnet yet):** Call `submit_tx` with a manually crafted no-op or use a devnet endpoint. Confirm the function returns a signature string without throwing.

---

## Step 5 — `jupiter.py`: Compose Full `execute_swap()` Function

**Goal:** Single function that orchestrates Steps 1–4 end-to-end.

**What to build:**
- Function `execute_swap(token_mint: str, amount_usd: float, wallet_pubkey: str) -> dict`
  ```python
  quote = get_quote(token_mint, amount_usd)
  base64_tx = build_swap_tx(quote, wallet_pubkey)
  signed = sign_tx(base64_tx)
  signature = submit_tx(signed)
  confirmed = confirm_tx(signature)
  return {
      "success": confirmed,
      "signature": signature,
      "token_mint": token_mint,
      "amount_usd": amount_usd,
      "out_amount": quote["outAmount"]
  }
  ```
- Add a `DRY_RUN` flag in config — if `True`, skip `submit_tx` and return a fake signature. This is your paper trading mode.

**Test:** Run with `DRY_RUN=True`. Confirm the returned dict has all fields populated correctly.

---

## Step 6 — Database: Add `proposals` and `positions` Tables

**Goal:** Set up the SQLite schema needed by the approval flow.

**What to build:**
- In `database/models.py`, define SQLAlchemy models:
  - `Proposal`: id, type, token_mint, token_symbol, source_wallet, suggested_size, take_profit (JSON string), stop_loss, confidence, reasoning, status, created_at, approved_at, executed_at, tx_signature
  - `Position`: id, proposal_id (FK), token_mint, token_symbol, entry_price_sol, entry_size_usd, entry_tx, current_price, unrealized_pnl, status, exit_price_sol, realized_pnl, exit_tx, opened_at, closed_at
- In `database/db.py`, create SQLite engine + `Base.metadata.create_all()`
- Add a helper `get_db()` dependency for FastAPI

**Test:** Run `db.py` standalone. Confirm both tables are created in `solsniper.db` by inspecting with `sqlite3` CLI.

---

## Step 7 — Router: `proposals.py` — Read Endpoints

**Goal:** Expose read-only proposal endpoints before wiring write logic.

**What to build:**
- `GET /proposals` — return all proposals with `status = 'pending'`, ordered by `created_at DESC`
- `GET /proposals/{id}` — return a single proposal by ID
- Both return Pydantic response models (define `ProposalOut` schema)

**Test:** Manually insert a fake proposal row into SQLite, start FastAPI, hit `GET /proposals` with `curl` or Swagger UI (`/docs`). Confirm the row comes back as JSON.

---

## Step 8 — Router: `proposals.py` — Approve Endpoint

**Goal:** `POST /proposals/{id}/approve` triggers Jupiter execution and opens a position.

**What to build:**
- Fetch proposal by ID, verify `status == 'pending'`
- Call `execute_swap(token_mint, suggested_size, wallet_pubkey)` from `jupiter.py`
- On success:
  - Update proposal: `status = 'executed'`, `approved_at = now()`, `executed_at = now()`, `tx_signature = sig`
  - Create a new `Position` row: entry details from quote, `status = 'open'`
- On failure:
  - Update proposal: `status = 'failed'`
  - Return HTTP 500 with error detail
- Return updated proposal + position as JSON

**Test (DRY_RUN=True):** Hit `POST /proposals/1/approve`. Confirm proposal status changes to `'executed'` in DB and a new position row appears.

---

## Step 9 — Router: `proposals.py` — Reject Endpoint

**Goal:** `POST /proposals/{id}/reject` marks a proposal as rejected.

**What to build:**
- Fetch proposal by ID, verify `status == 'pending'`
- Update: `status = 'rejected'`
- Return updated proposal

**Test:** Reject a pending proposal, confirm status in DB.

---

## Step 10 — Router: `portfolio.py`

**Goal:** Expose portfolio state — open positions and trade history.

**What to build:**
- `GET /portfolio/positions` — all positions where `status = 'open'`; include live `unrealized_pnl` field (fetched from DB, updated by background task)
- `GET /portfolio/history` — all closed positions; include `realized_pnl`, `entry_price_sol`, `exit_price_sol`, `opened_at`, `closed_at`
- `POST /portfolio/positions/{id}/close` — trigger a sell swap via Jupiter (swap token back to SOL), update position to `status = 'closed'`, record `exit_price_sol` and `realized_pnl`
- `GET /portfolio/summary` — aggregate stats: total realized P&L, win rate, best trade, worst trade, open position count

**Test:** Insert a fake open position, hit each endpoint, confirm correct data shape.

---

## Step 11 — Router: `wallets.py`

**Goal:** CRUD for the whale watchlist.

**What to build:**
- `GET /wallets` — list all watched wallets with score, win rate, avg P&L, last_seen
- `POST /wallets` — add a wallet; body: `{ "address": "...", "label": "optional" }`; validate address is valid base58 (44 chars); return created row
- `DELETE /wallets/{address}` — remove wallet from watchlist
- `GET /wallets/{address}/history` — return last 20 swap events for this wallet (from `whale_trades` table, populated by background task)

**Test:** Add a wallet, list it, delete it. Confirm DB state matches at each step.

---

## Step 12 — Background Task: `whale_poll.py`

**Goal:** Continuously poll Helius for tracked whale wallets and generate proposals.

**What to build:**
- Async function `run_whale_poll()` — infinite loop with `asyncio.sleep(30)`
- On each tick:
  1. Fetch all wallets from `watched_wallets` table
  2. For each wallet, call `helius.get_wallet_swaps(address, since=last_seen_signature)`
  3. For each new swap that is a BUY:
     - Fetch token data from DexScreener
     - Run RugCheck safety check
     - Call `whale_scorer.score_wallet(wallet)` to get current score
     - If score > threshold (configurable, default 60): call `whale_agent.propose(...)` → get structured proposal
     - Insert proposal into DB with `status = 'pending'`
     - Push to WebSocket hub (see Step 14)
  4. Update `last_seen` signature per wallet
- Register task on FastAPI `startup` event using `asyncio.create_task()`

**Test:** Add one real whale wallet, run the task for 2 minutes, check if any swap events are logged.

---

## Step 13 — Background Task: `sniper_poll.py`

**Goal:** Listen to PumpDev WebSocket for new token launches and generate proposals.

**What to build:**
- Async function `run_sniper_listener()` — persistent WebSocket connection to `wss://pumpdev.io/ws`
- On connect: send `{"method": "subscribeNewToken"}`
- On each new token event:
  1. Wait 60 seconds (let DexScreener index the pair)
  2. Fetch pair data from DexScreener using the mint
  3. Run `launch_scorer.score(token_data)` → get numeric score
  4. If score < 50: discard silently
  5. Run RugCheck + Solscan safety checks
  6. If any HIGH RISK flag: discard
  7. Call `sniper_agent.propose(...)` → get structured proposal
  8. Insert proposal into DB with `status = 'pending'`
  9. Push to WebSocket hub
- Auto-reconnect: wrap the WS loop in a `try/except`, reconnect with 5s backoff on disconnect
- Register task on FastAPI `startup` event

**Test:** Run the listener, observe new token events being logged to console for 5 minutes.

---

## Step 14 — Background Task: `position_updater.py`

**Goal:** Keep open position P&L fresh in the DB.

**What to build:**
- Async function `run_position_updater()` — loop with `asyncio.sleep(60)`
- On each tick:
  1. Fetch all positions where `status = 'open'`
  2. For each, call DexScreener for current price of `token_mint`
  3. Compute `unrealized_pnl = (current_price - entry_price_sol) / entry_price_sol * 100`
  4. Update `current_price` and `unrealized_pnl` in DB
  5. Check TP/SL conditions:
     - If `unrealized_pnl >= take_profit_pct[0]`: push a "TP hit" WebSocket event to UI (notification only — you still close manually or via the close button)
     - If `unrealized_pnl <= -stop_loss_pct`: push a "SL hit" WebSocket event
- Register on FastAPI startup

**Test:** Insert an open position with a known token, run for 2 minutes, confirm `current_price` updates in DB.

---

## Step 15 — WebSocket Hub (`routers/ws.py`)

**Goal:** Single WebSocket endpoint that broadcasts all real-time events to the frontend.

**What to build:**
- `ConnectionManager` class:
  ```python
  class ConnectionManager:
      def __init__(self):
          self.active_connections: list[WebSocket] = []
      
      async def connect(self, ws: WebSocket):
          await ws.accept()
          self.active_connections.append(ws)
      
      def disconnect(self, ws: WebSocket):
          self.active_connections.remove(ws)
      
      async def broadcast(self, message: dict):
          for connection in self.active_connections:
              await connection.send_json(message)
  ```
- Export a singleton `manager = ConnectionManager()`
- FastAPI route: `WS /ws/feed` — accept connection, keep alive, handle disconnect
- Import `manager` in background tasks (Steps 12, 13, 14) and call `await manager.broadcast({...})` when events fire

**Event types to broadcast:**
```json
{ "type": "new_proposal", "data": { ...proposal } }
{ "type": "proposal_expired", "data": { "id": 42 } }
{ "type": "position_update", "data": { "id": 7, "unrealized_pnl": 12.4, "current_price": 0.0003 } }
{ "type": "tp_hit", "data": { "position_id": 3, "token_symbol": "TKN", "pnl_pct": 120 } }
{ "type": "sl_hit", "data": { "position_id": 5, "token_symbol": "RUG", "pnl_pct": -48 } }
{ "type": "trade_executed", "data": { ...position } }
```

**Test:** Open the WS endpoint in a browser WebSocket tester (e.g., `wscat -c ws://localhost:8000/ws/feed`). Manually call `manager.broadcast(...)` from a test script. Confirm message arrives.

---

## Step 16 — Proposal Expiry Task

**Goal:** Auto-expire pending proposals that weren't actioned in time.

**What to build:**
- Async function `run_expiry_checker()` — loop with `asyncio.sleep(30)`
- Query: all proposals where `status = 'pending'` AND `created_at < now() - PROPOSAL_EXPIRY_SECONDS`
- For each: update `status = 'expired'`, broadcast `{ "type": "proposal_expired", "data": { "id": ... } }`
- Register on FastAPI startup

**Test:** Insert a proposal with `created_at` set to 10 minutes ago, run the task, confirm status changes to `'expired'` and WS event fires.

---

## Step 17 — `main.py`: Wire Everything Together

**Goal:** Single entrypoint that starts all tasks and mounts all routers.

**What to build:**
```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio

from routers import proposals, portfolio, wallets, ws
from tasks.whale_poll import run_whale_poll
from tasks.sniper_poll import run_sniper_listener
from tasks.position_updater import run_position_updater
from tasks.expiry import run_expiry_checker
from database.db import engine, Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    asyncio.create_task(run_whale_poll())
    asyncio.create_task(run_sniper_listener())
    asyncio.create_task(run_position_updater())
    asyncio.create_task(run_expiry_checker())
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(proposals.router)
app.include_router(portfolio.router)
app.include_router(wallets.router)
app.include_router(ws.router)
```

**Test:** `uvicorn main:app --reload`. Confirm all routers appear in `/docs`, all tasks start without errors in console.

---

## Step 18 — End-to-End Paper Trade Test (5 Proposals)

**Goal:** Verify the full pipeline works — from live data → agent proposal → UI → approve → execution (dry run) → position opened.

**Checklist:**
- [ ] `DRY_RUN=True` in `.env`
- [ ] At least 3 whale wallets added to watchlist
- [ ] PumpDev listener running and logging new tokens to console
- [ ] WebSocket connection confirmed open (use wscat or browser devtools)
- [ ] Wait for 5 proposals to appear (mix of whale copy + snipe)
- [ ] Approve 3 of them via `POST /proposals/{id}/approve`
- [ ] Reject 2 via `POST /proposals/{id}/reject`
- [ ] Confirm in DB: 3 positions with `status = 'open'`, 2 proposals with `status = 'rejected'`
- [ ] Confirm position P&L updates after 60 seconds (position updater task)
- [ ] Confirm WebSocket broadcasts `position_update` events
- [ ] Manually trigger a close via `POST /portfolio/positions/{id}/close`, confirm position moves to `status = 'closed'` with `realized_pnl` populated
- [ ] Check `/portfolio/summary` returns correct aggregate stats

**Only after all 5 paper trades pass cleanly: flip `DRY_RUN=False` for Week 5 live testing.**
