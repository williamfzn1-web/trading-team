"""Fetch live market context from Bitget public API for analyst enrichment."""

import asyncio
import httpx
from datetime import datetime, timedelta

_BASE = "https://api.bitget.com"
_CACHE: dict = {}
_CACHE_TTL = 60  # seconds


async def _get(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=8) as client:
        r = await client.get(f"{_BASE}{path}", params=params)
        r.raise_for_status()
        return r.json()


def _expired(key: str) -> bool:
    ts = _CACHE.get(f"{key}_ts")
    return ts is None or (datetime.utcnow() - ts).total_seconds() > _CACHE_TTL


async def get_funding_rate(symbol: str = "BTCUSDT") -> dict:
    key = f"funding_{symbol}"
    if not _expired(key):
        return _CACHE[key]
    try:
        data = await _get(
            "/api/v2/mix/market/current-fund-rate",
            {"symbol": symbol, "productType": "USDT-FUTURES"},
        )
        result = {
            "symbol": symbol,
            "rate": float(data["data"]["fundingRate"]) * 100,  # as percent
            "next_funding_time": data["data"].get("nextFundingTime", ""),
        }
    except Exception as e:
        print(f"[bitget_data] funding rate error: {e}")
        result = {"symbol": symbol, "rate": 0.01, "next_funding_time": ""}
    _CACHE[key] = result
    _CACHE[f"{key}_ts"] = datetime.utcnow()
    return result


async def get_long_short_ratio(symbol: str = "BTCUSDT", period: str = "1H") -> dict:
    key = f"lsr_{symbol}_{period}"
    if not _expired(key):
        return _CACHE[key]
    try:
        data = await _get(
            "/api/v2/mix/market/long-short-ratio",
            {"symbol": symbol, "period": period, "productType": "USDT-FUTURES"},
        )
        rows = data.get("data", [])
        latest = rows[-1] if rows else {}
        long_pct = float(latest.get("longAccountRatio", 0.5)) * 100
        result = {
            "long_pct": round(long_pct, 1),
            "short_pct": round(100 - long_pct, 1),
            "sentiment": (
                "bullish"
                if long_pct > 55
                else ("bearish" if long_pct < 45 else "neutral")
            ),
        }
    except Exception as e:
        print(f"[bitget_data] long-short ratio error: {e}")
        result = {"long_pct": 50.0, "short_pct": 50.0, "sentiment": "neutral"}
    _CACHE[key] = result
    _CACHE[f"{key}_ts"] = datetime.utcnow()
    return result


async def get_open_interest(symbol: str = "BTCUSDT") -> dict:
    key = f"oi_{symbol}"
    if not _expired(key):
        return _CACHE[key]
    try:
        data = await _get(
            "/api/v2/mix/market/open-interest",
            {"symbol": symbol, "productType": "USDT-FUTURES"},
        )
        oi = (
            float(data["data"]["openInterestList"][0]["size"])
            if data.get("data")
            else 0
        )
        result = {"open_interest": oi}
    except Exception as e:
        print(f"[bitget_data] open interest error: {e}")
        result = {"open_interest": 0}
    _CACHE[key] = result
    _CACHE[f"{key}_ts"] = datetime.utcnow()
    return result


async def get_market_context() -> dict:
    """Fetch all Bitget signals in parallel for use in analyst messages."""
    funding, lsr, oi = await asyncio.gather(
        get_funding_rate("BTCUSDT"),
        get_long_short_ratio("BTCUSDT"),
        get_open_interest("BTCUSDT"),
        return_exceptions=True,
    )

    def safe(v, default):
        return default if isinstance(v, Exception) else v

    funding = safe(funding, {"rate": 0.01})
    lsr = safe(lsr, {"long_pct": 50.0, "short_pct": 50.0, "sentiment": "neutral"})
    oi = safe(oi, {"open_interest": 0})

    rate = funding["rate"]
    long_pct = lsr["long_pct"]
    sentiment = lsr["sentiment"]

    # Build a short human-readable summary for injection into prompts
    funding_bias = "longs paying" if rate > 0 else "shorts paying"
    summary = (
        f"Bitget live data — "
        f"Funding: {rate:+.4f}% ({funding_bias}), "
        f"Long/Short: {long_pct:.1f}%/{lsr['short_pct']:.1f}% ({sentiment}), "
        f"OI: {oi['open_interest']:,.0f} BTC"
    )

    return {
        "funding_rate": rate,
        "funding_bias": funding_bias,
        "long_pct": long_pct,
        "short_pct": lsr["short_pct"],
        "sentiment": sentiment,
        "open_interest": oi["open_interest"],
        "summary": summary,
    }
