<div align="center">

# 🎯 SolSniper

**Semi-autonomous Solana Trading Agent**  
*Powered by Kimi K2 · Built on nanobot · Runs locally*

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Solana](https://img.shields.io/badge/Solana-9945FF?logo=solana&logoColor=white)](https://solana.com)
[![License](https://img.shields.io/badge/License-Private-red)]()

</div>

---

## What is SolSniper?

SolSniper is a **personal, semi-autonomous trading assistant** for the Solana ecosystem. It runs two parallel AI-powered agents that scan the chain for alpha — one tracks high-profit wallets, the other snipes new token launches. Every trade proposal lands in a clean React UI where **you** approve or reject before execution. No blind automation. No leaked keys. Pure local alpha.

> ⚠️ **This is experimental software for personal use only.** Start with $5–$10 positions. Most new tokens fail.

---

## 🧠 Two-Agent Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      SolSniper Engine                        │
├──────────────────────────┬──────────────────────────────────┤
│    🐋 Whale Tracker      │      🚀 Token Sniper             │
│                          │                                  │
│  Helius Wallet API       │   PumpDev WebSocket              │
│  ↓                       │   ↓                              │
│  Parse SWAP events       │   New token detected             │
│  ↓                       │   ↓                              │
│  Score P&L / Win rate    │   DexScreener pair data          │
│  ↓                       │   ↓                              │
│  Kimi K2 evaluates       │   Numeric launch score           │
│  ↓                       │   ↓                              │
│  COPY TRADE proposal     │   RugCheck + Solscan safety      │
│     ($50 max)            │   ↓                              │
│                          │   Kimi K2 evaluates              │
│                          │   ↓                              │
│                          │   SNIPE proposal ($50 max)       │
├──────────────────────────┴──────────────────────────────────┤
│              📋 Proposal Queue → React UI                    │
│                   [Approve]  [Reject]                        │
│                         ↓                                  │
│              Jupiter Swap API → On-chain                     │
└─────────────────────────────────────────────────────────────┘
```

---

## ✨ Features

### 🐋 Whale Tracker Agent
- **Monitors** a curated list of high-profit Solana wallets via Helius API
- **Scores** each wallet by win rate, average realized P&L, recency, and trade frequency
- **Detects** buy/sell swaps in real time (30s polling)
- **Proposes** copy trades adjusted to your volume ($50 max default) with auto TP/SL levels
- Tracks open positions and unrealized P&L

### 🚀 Token Sniper Agent
- **Listens** to PumpDev WebSocket for brand-new token launches (~500ms latency)
- **Scores** launches on volume velocity, buy pressure, liquidity depth, age, and safety
- **Screens** every candidate through RugCheck.xyz + Solscan holder analysis
- **Proposes** snipe entries with layered take-profit targets
- Auto-discards honeypots, mint-authority tokens, and concentrated supply rugs

### 🖥️ React Dashboard
- **Live Feed** — real-time proposal cards with countdown timers
- **Portfolio** — open positions, unrealized P&L, equity curve
- **Whale Watchlist** — add/remove wallets, see scores & history
- **Settings** — position size, slippage, thresholds, API keys
- **WebSocket** — instant updates, no page refresh

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **Agent Framework** | `nanobot` (multi-agent orchestration) |
| **LLM** | Kimi K2 via API |
| **Whale Data** | Helius Wallet API (1M credits/mo free) |
| **New Token Feed** | PumpDev WebSocket (free, no key) |
| **Token Pair Data** | DexScreener REST API (free, no key) |
| **Safety / Red Flags** | RugCheck.xyz API + Solscan API |
| **Swap Execution** | Jupiter Swap API v6 (free) |
| **Backend** | FastAPI + native WebSockets + asyncio |
| **Database** | SQLite (SQLAlchemy ORM) |
| **Frontend** | React 18 + Vite + Tailwind CSS + Recharts |
| **Runtime** | Python 3.11+, Node 20+ |

---

## 🚀 Quick Start

### 1. Clone & Setup Backend

```bash
git clone https://github.com/EliaszDev/solsniper.git
cd solsniper

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy env template and fill in your keys
cp .env.example .env
# Edit .env with your real API keys
```

### 2. Setup Frontend

```bash
cd frontend
npm install
npm run dev
```

### 3. Run Backend

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Open Dashboard

Navigate to `http://localhost:5173` — the React dev server proxies API calls to FastAPI automatically.

---

## ⚙️ Configuration

Edit `.env` with your credentials:

```env
HELIUS_API_KEY=your_helius_key
WALLET_PRIVATE_KEY=your_base58_keypair
KIMI_API_KEY=your_kimi_key
KIMI_API_BASE=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k2

# Trading limits
MAX_POSITION_SIZE_USD=50
MIN_SNIPE_SCORE=50
PROPOSAL_EXPIRY_SECONDS=180
SLIPPAGE_BPS=300
```

> 🔒 **Never commit `.env` to git.** It is already ignored by `.gitignore`.

---

## 📡 API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | System status |
| `GET` | `/proposals` | List pending proposals |
| `POST` | `/proposals/{id}/approve` | Approve & execute via Jupiter |
| `POST` | `/proposals/{id}/reject` | Reject proposal |
| `GET` | `/portfolio/positions` | Open positions + live P&L |
| `GET` | `/portfolio/history` | Closed trade history |
| `GET` | `/wallets` | Whale watchlist |
| `POST` | `/wallets` | Add wallet to watchlist |
| `DELETE` | `/wallets/{address}` | Remove wallet |
| `WS` | `/ws/feed` | Live proposal + position stream |

---

## 🗓 Build Roadmap

| Week | Milestone |
|---|---|
| **Week 1** | Data layer — Helius client, PumpDev WS, DexScreener client |
| **Week 2** | Scoring engines + Kimi K2 agent integration |
| **Week 3** | Jupiter execution + FastAPI backend + WebSocket hub |
| **Week 4** | React frontend — Feed, Portfolio, Watchlist |
| **Week 5** | Live testing ($5–$10), polish, audio alerts |
| **Week 6** | Tuning thresholds, backtesting script, documentation |

---

## ⚠️ Risk & Safety Notes

- **Start small.** Use `MAX_POSITION_SIZE_USD=10` for the first week of live trading.
- **New token sniping is high risk.** Most launches fail. Treat snipe proposals as lottery tickets with asymmetric payoff.
- **Whale copy-trading has lag.** 30-second polling + agent processing means you enter after the whale. Works better for mid-caps than instant-dump micro-caps.
- **Slippage matters.** 3% default may need to increase for thin liquidity. Jupiter will fail the quote if it can't fill within tolerance.
- **Your keys stay local.** The private key is loaded from `.env` at startup and never logged or transmitted anywhere except Solana transaction signing.

---

## 📜 License

Private / Personal use only. Not open source.

---

<div align="center">

Built with 🧠 by EliaszDev · Powered by Kimi K2

</div>
