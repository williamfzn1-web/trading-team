"""Paginated historical OHLCV from Binance public data endpoint."""

import asyncio
import json
import time
import urllib.request

SYMBOL_MAP = {
    "BTC/USDT": "BTCUSDT",
    "ETH/USDT": "ETHUSDT",
    "SOL/USDT": "SOLUSDT",
    "BNB/USDT": "BNBUSDT",
    "AVAX/USDT": "AVAXUSDT",
    "XRP/USDT": "XRPUSDT",
    "ADA/USDT": "ADAUSDT",
    "DOT/USDT": "DOTUSDT",
    "LINK/USDT": "LINKUSDT",
    "MATIC/USDT": "MATICUSDT",
}

_SPOT_KLINES = "https://data-api.binance.vision/api/v3/klines"
_FUTURES_KLINES = "https://fapi.binance.com/fapi/v1/klines"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# In-memory cache: symbol_interval_days -> (fetched_at, candles)
_cache: dict[str, tuple[float, list]] = {}
CACHE_TTL = 3600  # 1 hour


def _fetch_sync(url: str) -> list | None:
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


async def fetch_historical_ohlcv(
    symbol: str,
    interval: str = "1h",
    days: int = 540,
) -> list:
    """
    Returns [[ts_ms, open, high, low, close, volume], ...] sorted oldest-first.
    Paginates automatically (Binance limit = 1000 per request).
    Cached for 1 hour.
    """
    cache_key = f"{symbol}_{interval}_{days}"
    cached = _cache.get(cache_key)
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]

    binance_sym = SYMBOL_MAP.get(symbol, symbol.replace("/", ""))
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - days * 24 * 3600 * 1000

    all_candles: list = []
    current_start = start_ms
    loop = asyncio.get_event_loop()

    while current_start < end_ms:
        raw = None
        for base_url in (_SPOT_KLINES, _FUTURES_KLINES):
            params = (
                f"?symbol={binance_sym}&interval={interval}"
                f"&startTime={current_start}&endTime={end_ms}&limit=1000"
            )
            raw = await loop.run_in_executor(None, _fetch_sync, base_url + params)
            if raw:
                break

        if not raw:
            print(f"[hist] {symbol} both endpoints failed")
            break

        chunk = [
            [int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])]
            for r in raw
        ]
        all_candles.extend(chunk)
        current_start = chunk[-1][0] + 1

        if len(raw) < 1000:
            break  # no more pages

        await asyncio.sleep(0.05)  # gentle rate limit

    if all_candles:
        _cache[cache_key] = (time.time(), all_candles)
        print(f"[hist] {symbol} {len(all_candles)} bars ({days}d {interval})")

    return all_candles


async def fetch_historical_multi(
    symbols: list[str], interval: str = "1h", days: int = 540
) -> dict:
    """Fetch multiple symbols concurrently."""
    results = await asyncio.gather(
        *[fetch_historical_ohlcv(s, interval, days) for s in symbols],
        return_exceptions=True,
    )
    return {sym: (r if isinstance(r, list) else []) for sym, r in zip(symbols, results)}
