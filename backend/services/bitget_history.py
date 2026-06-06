"""Historical Bitget market data for backtest Bitget filter integration."""

import asyncio
import time
import httpx
from bisect import bisect_right

_BASE = "https://api.bitget.com"
_CACHE: dict = {}
_CACHE_TTL = 3600  # 1 hour


async def _fetch_funding_history(symbol: str, days: int) -> list:
    """Returns [{ts, rate}, ...] sorted oldest-first. Rate in percent."""
    all_rates = []
    page = 1
    cutoff_ms = int((time.time() - days * 86400) * 1000)

    async with httpx.AsyncClient(timeout=15) as client:
        while True:
            try:
                r = await client.get(
                    f"{_BASE}/api/v2/mix/market/history-fund-rate",
                    params={
                        "symbol": symbol,
                        "productType": "USDT-FUTURES",
                        "pageSize": 100,
                        "pageNo": page,
                    },
                )
                rows = r.json().get("data", [])
                if not rows:
                    break
                for row in rows:
                    ts = int(row["fundingTime"])
                    rate = float(row["fundingRate"]) * 100
                    all_rates.append({"ts": ts, "rate": rate})
                if len(rows) < 100:
                    break
                if min(r["ts"] for r in all_rates) <= cutoff_ms:
                    break
                page += 1
            except Exception as e:
                print(f"[bitget_history] funding page {page}: {e}")
                break

    result = [r for r in all_rates if r["ts"] >= cutoff_ms]
    result.sort(key=lambda x: x["ts"])
    print(f"[bitget_history] funding: {len(result)} records ({days}d)")
    return result


async def _fetch_lsr_history(symbol: str, days: int) -> list:
    """Returns [{ts, long_pct}, ...] sorted oldest-first."""
    cutoff_ms = int((time.time() - days * 86400) * 1000)
    result = []

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(
                f"{_BASE}/api/v2/mix/market/long-short-ratio",
                params={
                    "symbol": symbol,
                    "productType": "USDT-FUTURES",
                    "period": "1H",
                },
            )
            rows = r.json().get("data", [])
            for row in rows:
                ts = int(row.get("ts", 0))
                if ts >= cutoff_ms:
                    long_pct = float(row.get("longAccountRatio", 0.5)) * 100
                    result.append({"ts": ts, "long_pct": round(long_pct, 1)})
        except Exception as e:
            print(f"[bitget_history] LSR: {e}")

    result.sort(key=lambda x: x["ts"])
    print(f"[bitget_history] LSR: {len(result)} records")
    return result


async def get_backtest_bitget_history(symbol: str = "BTCUSDT", days: int = 180) -> dict:
    """Fetch funding + LSR history in parallel. Cached 1 hour."""
    key = f"{symbol}_{days}"
    cached = _CACHE.get(key)
    if cached and time.time() - cached[0] < _CACHE_TTL:
        return cached[1]

    funding, lsr = await asyncio.gather(
        _fetch_funding_history(symbol, days),
        _fetch_lsr_history(symbol, days),
        return_exceptions=True,
    )
    funding = funding if isinstance(funding, list) else []
    lsr = lsr if isinstance(lsr, list) else []

    data = {
        "funding": funding,
        "lsr": lsr,
        "funding_ts": [r["ts"] for r in funding],
        "lsr_ts": [r["ts"] for r in lsr],
    }
    _CACHE[key] = (time.time(), data)
    return data


def lookup_bitget_ctx(ts_ms: int, history: dict) -> dict | None:
    """Return the most recent Bitget context at or before ts_ms. None if no data."""
    funding_list = history.get("funding", [])
    lsr_list = history.get("lsr", [])
    funding_ts = history.get("funding_ts", [])
    lsr_ts = history.get("lsr_ts", [])

    rate = None
    if funding_ts:
        idx = bisect_right(funding_ts, ts_ms) - 1
        if idx >= 0:
            rate = funding_list[idx]["rate"]

    long_pct = None
    if lsr_ts:
        idx = bisect_right(lsr_ts, ts_ms) - 1
        if idx >= 0:
            long_pct = lsr_list[idx]["long_pct"]

    if rate is None and long_pct is None:
        return None

    rate = rate if rate is not None else 0.01
    long_pct = long_pct if long_pct is not None else 50.0

    return {
        "funding_rate": rate,
        "long_pct": long_pct,
        "short_pct": round(100 - long_pct, 1),
        "open_interest": 0,
    }
