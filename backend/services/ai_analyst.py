"""Generate analyst group-chat messages via Claude API (haiku). Falls back to templates."""

import os
import random
from datetime import datetime

# Fallback templates per strategy — used when API key absent or call fails
_TEMPLATES: dict[str, list[str]] = {
    "SMC": [
        "BTC showing a clear Order Block at the recent swing low. Price swept sell-side liquidity before reclaiming — classic inducement pattern. Watching for CHoCH on H1 to confirm long.",
        "ETH bearish OB holding at resistance. FVG sitting unfilled below current price. Distribution structure intact — staying short bias.",
        "BTC printed a bullish BOS on H4. Last bearish candle before the impulse is our OB — price returning to fill the gap. Setting limit long at the OB mid.",
    ],
    "Auction Theory": [
        "BTC value area building between key levels. Price currently at VAL — auction theory says buyers should defend here. POC is the magnet target.",
        "Market found acceptance above yesterday's VAH. Thin air above — single prints suggest quick move if we get continuation. Staying long.",
        "Price rejected from naked POC twice now. This level is key. Break and close above opens a clean path to the next distribution.",
    ],
    "Order Flow": [
        "ETH CVD showing hidden bullish divergence — price made new lows but cumulative delta didn't confirm. Large bids absorbing at this level. Scaling in long.",
        "Bearish delta spike on BTC. Sellers stepped in aggressively on that last rip. Volume imbalance suggests continuation lower — staying short.",
        "Order flow turning bullish on SOL. Buy market orders overwhelming sellers. Volume surge with price holding = institutional accumulation.",
    ],
    "On-chain Data": [
        "On-chain SOPR proxy crossed above 1.0 after weeks below — holders now back in profit and less likely to sell. Historically a re-accumulation signal.",
        "Exchange netflow proxy turning negative — coins leaving exchanges. Supply shock building. This setup historically precedes significant upside.",
        "NUPL proxy in the belief-denial zone. Not euphoric yet. Long-term holders accumulating at these levels per on-chain signals.",
    ],
    "Arbitrage": [
        "BTC/ETH ratio z-score hitting 2 std dev — BTC significantly overvalued relative to ETH on a 30-day basis. Fading the premium with a short BTC position.",
        "Funding rate proxy at extreme — RSI divergence signaling long squeeze risk. Positioning short here with tight stops.",
        "Ratio mean-reverting as expected. ETH catching up to BTC move. Closing the pair trade with +2.3% gain.",
    ],
    "Whale Hunting": [
        "Massive volume spike on BTC — 3× average. Up candle with close near high. Whale accumulation pattern. Following the smart money long.",
        "Large player distribution detected near $67K round number. Three consecutive high-volume bearish candles. Stepping aside from longs.",
        "Quiet accumulation setup: 5 consecutive low-volume closes all above EMA21. Classic absorption before markup. Adding to long.",
    ],
    "Capital Flow": [
        "Capital rotating back into BTC — dominance proxy rising as alts underperform. Risk-off regime. BTC long is the play right now.",
        "Altcoins outperforming BTC significantly on 30-day basis. Risk-on rotation in full swing. Lightening BTC exposure.",
        "Stablecoin dry-powder ignition: volume lull followed by a surge today. New money entering the market. Bullish for BTC near-term.",
    ],
    "Liquidity": [
        "Equal lows cluster identified below current price — classic sell-side liquidity pool. Expecting a sweep of those stops before a sharp reversal long.",
        "BSL swept above last week's high. Institutions grabbed the stops, now price closed back below — bearish reversal confirmed. Short entry.",
        "Price consolidating just above a major SSL zone. If we sweep and reclaim, it's an A+ long setup. Watching carefully.",
    ],
    "Macro/Sentiment": [
        "Macro structure remains bullish — EMA50 > EMA100 > EMA200 on the daily proxy. This dip into EMA50 is a buying opportunity, not a trend change.",
        "Fear & Greed proxy in extreme greed while macro trend is bearish. Classic distribution. Shorting the rip with wide stops.",
        "Volatility compression for 8 candles now. Coil building. When it breaks, it'll be fast. Positioned for upside given macro backdrop.",
    ],
}


async def generate_message(
    analyst, current_prices: dict, open_trades: list
) -> tuple[str, str]:
    """Returns (message_content, message_type). Tries Claude API first."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        try:
            return await _claude_message(analyst, current_prices, open_trades, api_key)
        except Exception as e:
            print(f"[ai_analyst] Claude API error for {analyst.name}: {e}")

    return _fallback_message(analyst, open_trades)


async def _claude_message(
    analyst, prices: dict, open_trades: list, api_key: str
) -> tuple[str, str]:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key)

    btc = prices.get("BTC/USDT", {})
    eth = prices.get("ETH/USDT", {})
    btc_p = btc.get("price", 0)
    btc_ch = btc.get("change_24h", 0)
    eth_p = eth.get("price", 0)

    pos_str = (
        ", ".join(
            f"{t.symbol} {t.side.upper()} @${t.entry_price:,.0f}" for t in open_trades
        )
        or "none"
    )

    msg_type = random.choice(["analysis", "signal", "alert"])

    prompt = (
        f"You are {analyst.name}, a crypto derivatives trader on a team of 10 specialists.\n"
        f"Your strategy: {analyst.strategy} — {analyst.strategy_description}\n"
        f"Market now: BTC ${btc_p:,.0f} ({btc_ch:+.1f}% 24h), ETH ${eth_p:,.0f}\n"
        f"Your open positions: {pos_str}\n\n"
        f"Post ONE concise message ({msg_type}) to the team group chat (2-4 sentences).\n"
        f"Be specific about price levels and patterns your strategy identifies.\n"
        f"Sound like a real trader — no filler phrases, no 'As a {analyst.strategy} trader...'."
    )

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=160,
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.content[0].text.strip()
    return content, msg_type


def _fallback_message(analyst, open_trades: list) -> tuple[str, str]:
    strategy = analyst.strategy
    templates = _TEMPLATES.get(
        strategy, ["Monitoring market conditions. No high-conviction setup yet."]
    )
    msg = random.choice(templates)

    # If analyst has an open position, sometimes append trade status
    if open_trades and random.random() > 0.5:
        t = random.choice(open_trades)
        msg += f" Currently holding {t.side.upper()} {t.symbol} from ${t.entry_price:,.0f}."

    msg_type = random.choice(["analysis", "signal", "alert"])
    return msg, msg_type


async def run_discussion_round(
    db_session_factory, current_prices: dict, n_speakers: int = 3
):
    """Pick N analysts to post a message this round."""
    from database import SessionLocal
    import models

    db = db_session_factory()
    try:
        analysts = db.query(models.Analyst).all()
        speakers = random.sample(analysts, min(n_speakers, len(analysts)))

        for analyst in speakers:
            open_trades = (
                db.query(models.Trade)
                .filter(
                    models.Trade.analyst_id == analyst.id, models.Trade.status == "open"
                )
                .all()
            )
            content, msg_type = await generate_message(
                analyst, current_prices, open_trades
            )
            msg = models.GroupMessage(
                analyst_id=analyst.id,
                content=content,
                message_type=msg_type,
                timestamp=datetime.utcnow(),
            )
            db.add(msg)
            safe = content[:80].encode("ascii", "replace").decode("ascii")
            print(f"[chat] {analyst.name} ({msg_type}): {safe}...")

        db.commit()
    except Exception as e:
        print(f"[ai_analyst] Discussion round error: {e}")
        db.rollback()
    finally:
        db.close()
