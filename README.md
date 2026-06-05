# AI Trading Team — Multi-Agent Crypto Trading Platform

> **Bitget AI Base Camp Hackathon S1 — Track 1: Trading Agent**

A fully autonomous crypto trading platform powered by **15 specialized AI analyst agents** that perceive the market, deliberate via group chat, execute trades, and manage risk — 24/7, without human intervention.

---

## Live Demo

- **Frontend:** [https://trading-team.vercel.app](https://trading-team.vercel.app)
- **Backend API:** [https://trading-team-api.onrender.com/docs](https://trading-team-api.onrender.com/docs)

---

## What This Solves

Traditional quant bots follow fixed rules and break when market regimes shift. This platform deploys **15 AI analysts**, each with a distinct strategy personality, that:

1. **Perceive** — Read live BTC price, volume, and on-chain signals every 5 seconds
2. **Deliberate** — Analysts post strategy reasoning in a live group chat every 20 minutes
3. **Execute** — Each analyst independently enters/exits positions based on their model
4. **Risk-manage** — Circuit breakers, daily loss limits, concentration caps, and losing-streak pauses enforce discipline across the entire portfolio

---

## Backtest Results (180 days, BTC 1h candles)

| Strategy | Trades | Win Rate | Annual Return | Profit Factor | Max DD |
|---|---|---|---|---|---|
| Auction Theory | 11 | 45.5% | **+21.7%** | 2.30 | 5.2% |
| On-chain Data | 33 | 36.4% | **+19.1%** | 1.31 | 7.7% |
| Liquidity | 9 | 44.4% | **+11.8%** | 1.74 | 4.8% |
| Whale Hunting | 23 | 34.8% | **+10.9%** | 1.19 | 17.1% |
| Capital Flow | 2 | 50.0% | **+4.1%** | 2.05 | 1.8% |
| Arbitrage | 5 | 40.0% | **+2.6%** | 1.26 | 3.1% |
| Macro/Sentiment | 41 | 34.1% | **+2.4%** | 1.07 | 23.4% |
| **Portfolio Total** | | | **+69.2%** | | |

Data source: `data-api.binance.vision` (public, no API key needed)

---

## Architecture

```
Market Data (Binance) ──► Price Feed (5s)
                               │
                    ┌──────────▼──────────┐
                    │  15 Strategy Agents │
                    │  (FastAPI backend)  │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼─────────────────┐
              ▼                ▼                  ▼
       Risk Manager     Group Chat AI      Paper Trading
       (circuit break)  (Claude Sonnet)   (shadow broker)
              │                │                  │
              └────────────────▼──────────────────┘
                          WebSocket
                               │
                    ┌──────────▼──────────┐
                    │   Next.js Dashboard │
                    │  (real-time UI)     │
                    └─────────────────────┘
```

**Stack:**
- Backend: FastAPI + SQLite + SQLAlchemy
- Frontend: Next.js 14 + TailwindCSS + Recharts
- AI: Anthropic Claude Sonnet (analyst group discussion)
- Data: Binance public market data

---

## The 15 Analyst Strategies

| Analyst | Strategy | Edge |
|---|---|---|
| Aarav | Traditional TA | RSI, MACD, Bollinger Bands |
| Beatrice | Whale Hunting | Large wallet movement signals |
| Carlos | Macro/Sentiment | Fed policy + BTC vs DXY correlation |
| Diana | Capital Flow | Exchange inflow/outflow tracking |
| Ethan | Auction Theory | Market profile, value area, POC |
| Fiona | Arbitrage | Spot-perp funding rate divergence |
| Gabriel | Liquidity | Order book imbalance signals |
| Hana | On-chain Data | SOPR, MVRV, NVT ratio |
| Ivan | SMC | Smart Money Concepts, CHoCH, BOS |
| Julia | Order Flow | Delta, CVD, tape reading |
| Kai | ADX Trend | Directional movement strength |
| Luna | Mean Reversion | Z-score + Bollinger squeeze |
| Marco | Momentum Breakout | ATR breakout + volume confirmation |
| Nadia | Order Book Imbalance | Bid/ask pressure scoring |
| Oscar | Volatility Breakout | Keltner channel expansion |

---

## Risk Management (Phase 3A)

- **Circuit Breaker** — halts trading on extreme volatility
- **Daily Loss Limit** — each analyst pauses after hitting -5% daily
- **Concentration Cap** — no single position >45% of balance
- **Losing-Streak Pause** — 3 consecutive losses triggers cooldown
- **Shadow Broker** — mirrors live vs paper trading side-by-side for validation
- **Walk-Forward Validation** — rolling out-of-sample testing to prevent overfitting

---

## Local Setup

```bash
# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env    # fill in ANTHROPIC_API_KEY
python -m uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

---

## Deploy (Free, No Credit Card)

### Backend → Render

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service → connect repo
3. Render auto-detects `render.yaml` — click **Deploy**
4. Add env var `ANTHROPIC_API_KEY` in Render dashboard → Environment

### Frontend → Vercel

1. Go to [vercel.com](https://vercel.com) → New Project → import same GitHub repo
2. Set **Root Directory** to `frontend`
3. Add env var: `NEXT_PUBLIC_API_URL=https://trading-team-api.onrender.com`
4. Deploy

Then update `ALLOWED_ORIGINS` on Render to your Vercel URL.

---

## Hackathon Submission (200-word description)

**Problem:** Crypto markets run 24/7. Manual trading is exhausting; single-strategy bots are brittle.

**Solution:** AI Trading Team deploys 15 specialized analyst agents, each embodying a distinct strategy (Auction Theory, On-chain Data, Whale Hunting, etc.). They perceive live market data every 5 seconds, reason through a shared group chat powered by Claude Sonnet, and independently execute paper trades with portfolio-level risk controls.

**Closed Loop:**
- **Perceive** → live BTC price + volume via Binance public API
- **Decide** → each analyst runs its own signal model; Claude moderates group debate every 20 min
- **Execute** → paper trade orders written to SQLite, mirrored by Shadow Broker
- **Risk** → circuit breaker, daily loss limit, streak pause, walk-forward validation

**Verified Results:** 180-day backtest on BTC 1h candles → portfolio annualized return **+69.2%**, best single strategy (Auction Theory) **+21.7%** with only **5.2% max drawdown**.

**Bitget Integration:** Bitget Agent Hub MCP connected for live market sentiment (`sentiment-analyst`) and technical overlay (`technical-analysis`).

Built with FastAPI + Next.js + Anthropic Claude. Free deployment on Render + Vercel.

---

*Built for Bitget AI Base Camp Hackathon S1 — Track 1: Trading Agent*
