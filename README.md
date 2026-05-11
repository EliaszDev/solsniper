# 🎯 SolSniper

> A semi-autonomous Solana trading agent powered by **Kimi K2**, built on the `nanobot` multi-agent framework.  
> Two brain modules — **Whale Tracker** & **Token Sniper** — find alpha, score it, and propose trades for your approval before execution.

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Solana](https://img.shields.io/badge/Solana-Mainnet-9945FF?logo=solana)](https://solana.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## ✨ What It Does

SolSniper runs two parallel agents that monitor the Solana chain in real time. Neither trades without **your explicit approval**.

### 🐋 Whale Tracker Agent
Monitors a curated list of high-profit wallets via the **Helius API**.
- Scores wallets by **win rate**, **average P&L**, and **recency**
- When a tracked whale buys a token → proposes a **copy trade** sized to your budget (default $50)
- Includes suggested **take-profit** and **stop-loss** levels

### 🚀 Token Sniper Agent
Listens to **PumpDev WebSocket** for brand-new token launches.
- Scores every launch on **volume velocity**, **buy pressure**, **liquidity depth**, and **safety**
- Flags rug risks via **RugCheck.xyz** + **Solscan** (mint authority, freeze authority, holder concentration)
- If the score passes threshold → proposes a **snipe entry** with layered TP targets

### 🖐️ Human-in-the-Loop
All proposals land in a **React UI** with a 3-minute countdown. You click **Approve** or **Reject**. No automated execution.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        React UI (Port 5173)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Live Feed   │  │  Portfolio   │  │  Whale Watchlist │  │
│  │  Approve/Rej │  │  Open Pos    │  │  Add / Remove    │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
└─────────┼─────────────────┼───────────────────┼────────────┘
          │                 │                   │
          └─────────────────┴───────────────────┘
                            │
                    WebSocket / REST
                            │
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Backend (Port 8000)               │
│                                                             │
│   ┌──────────────┐         ┌──────────────┐                │
│   │ Whale Agent  │◄────────┤ Helius API   │                │
│   │ (Kimi K2)    │         │ Wallet Hist. │                │
│   └──────┬───────┘         └──────────────┘                │
│          │                                                  │
│   ┌──────┴───────┐         ┌──────────────┐                │
│   │ Sniper Agent │◄────────┤ PumpDev WS   │                │
│   │ (Kimi K2)    │         │ DexScreener  │                │
│   └──────┬───────┘         └──────────────┘                │
│          │                                                  │
│   ┌──────┴───────┐         ┌──────────────┐                │
│   │  Proposal    │◄───────┤ RugCheck     │                │
│   │  Engine      │         │ Solscan      │                │
│   └──────┬───────┘         └──────────────┘                │
│          │                                                  │
│   ┌──────┴───────┐         ┌──────────────┐                │
│   │  Jupiter     │         │  SQLite      │                │
│   │  Swap API    │         │  (SQLAlchemy)│                │
│   └──────────────┘         └──────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Agent Framework | `nanobot` |
| LLM | Kimi K2 via API |
| Whale Data | Helius Wallet API (free tier) |
| New Token Feed | PumpDev WebSocket |
| Pair / Market Data | DexScreener REST API |
| Safety / Red Flags | RugCheck.xyz + Solscan API |
| Swap Execution | Jupiter Swap API v6 |
| Backend | FastAPI + WebSockets + `asyncio` |
| Database | SQLite (SQLAlchemy) |
| Frontend | React 18 + Tailwind CSS + Recharts |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- A Solana wallet keypair (paper trade mode works without real funds)
- Free API keys: [Helius](https://helius.xyz), [Kimi](https://platform.moonshot.cn)

### 1. Clone & Install

```bash
git clone https://github.com/EliaszDev/solsniper.git
cd solsniper

# Backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scriptsctivate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your keys:

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

> ⚠️ **Never commit `.env`**. It is already gitignored.

### 3. Run

```bash
# Terminal 1 — Backend
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Open `http://localhost:5173`.

---

## 📁 Repository Structure

```
solsniper/
├── backend/
│   ├── main.py              # FastAPI entrypoint + WebSocket hub
│   ├── config.py            # Pydantic settings from .env
│   ├── database/
│   │   ├── models.py        # SQLAlchemy ORM
│   │   └── db.py            # SQLite engine + sessions
│   ├── agents/
│   │   ├── base_agent.py    # Shared nanobot / Kimi K2 config
│   │   ├── whale_agent.py   # Whale Tracker logic
│   │   └── sniper_agent.py  # Token Sniper logic
│   ├── services/
│   │   ├── helius.py        # Helius API client
│   │   ├── dexscreener.py   # DexScreener REST client
│   │   ├── pumpdev_ws.py    # PumpDev WebSocket listener
│   │   ├── rugcheck.py      # Safety checks
│   │   └── jupiter.py       # Quote + swap execution
│   ├── scoring/
│   │   ├── whale_scorer.py  # Wallet P&L / win-rate engine
│   │   └── launch_scorer.py # Token launch score 0-100
│   ├── routers/
│   │   ├── proposals.py     # Approve / reject endpoints
│   │   ├── portfolio.py     # Positions + history
│   │   ├── wallets.py       # Watchlist CRUD
│   │   └── ws.py            # WebSocket feed
│   └── tasks/
│       ├── whale_poll.py    # Background wallet polling
│       └── sniper_poll.py   # Background PumpDev listener
├── frontend/
│   └── src/
│       ├── components/      # Feed, ProposalCard, Portfolio, etc.
│       ├── hooks/           # useWebSocket
│       └── api/             # Axios client
├── .env.example
├── requirements.txt
└── README.md
```

---

## 🔌 API Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/proposals` | List pending proposals |
| `POST` | `/proposals/{id}/approve` | Approve → Jupiter execution |
| `POST` | `/proposals/{id}/reject` | Reject proposal |
| `GET` | `/portfolio/positions` | Open positions + live P&L |
| `GET` | `/portfolio/history` | Closed trades |
| `GET` | `/wallets` | Whale watchlist |
| `POST` | `/wallets` | Add wallet |
| `DELETE` | `/wallets/{address}` | Remove wallet |
| `WS` | `/ws/feed` | Real-time proposal + position stream |

---

## 🤝 Contributing

We welcome contributors! Solana trading tooling is a community effort.

### How to Contribute

1. **Fork** the repo and clone your fork
2. Create a **feature branch**: `git checkout -b feature/amazing-thing`
3. **Install pre-commit hooks** (optional but appreciated):
   ```bash
   pip install pre-commit
   pre-commit install
   ```
4. Make your changes, add tests if applicable
5. **Commit** with clear messages: `feat: add holder concentration filter`
6. **Push** and open a **Pull Request** against `main`

### Good First Issues

Look for issues tagged `good first issue` or `help wanted`. Some ideas:
- Add more safety checks (honeypot detection, liquidity lock verification)
- Improve the launch scoring algorithm
- Add Telegram / Discord bot notifications
- Build a backtesting mode with historical DexScreener data
- Add multi-wallet portfolio aggregation

### Code Style
- **Python**: PEP 8, type hints encouraged, `black` + `ruff` formatting
- **React**: Functional components, Tailwind for styling

---

## ⚠️ Risk & Safety Notes

- **Start small.** The default `MAX_POSITION_SIZE_USD` is $50. Consider $5–$10 for your first live week.
- **New token sniping is high risk.** Most launches fail. Treat snipe proposals as lottery tickets with asymmetric payoff.
- **Whale copy-trading has lag.** 30-second polling + agent processing means you will not front-run the whale. This works better for mid-cap momentum than micro-cap dumps.
- **Never share your private key.** `.env` is gitignored, but double-check before pushing.
- **This is not financial advice.** SolSniper is an alpha research tool. You are responsible for every trade you approve.

---

## 📜 License

MIT — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- [Helius](https://helius.xyz) — Solana infrastructure & wallet APIs
- [DexScreener](https://dexscreener.com) — DEX pair data
- [PumpDev](https://pumpdev.io) — Real-time token launch stream
- [RugCheck](https://rugcheck.xyz) — Token safety reports
- [Jupiter](https://jup.ag) — Swap aggregation & execution
- [nanobot](https://github.com/HKUDS/nanobot) — Multi-agent framework
- [Kimi](https://www.kimi.com) — LLM backend

---

<p align="center">
  Built with 💜 by <a href="https://github.com/EliaszDev">EliaszDev</a> and contributors.
</p>
