"""Fetch and cache OHLCV candle data from Binance public data endpoint."""

import asyncio
import json
import time
import urllib.request

_cache: dict = {}
_cache_ts: dict = {}
CACHE_TTL = 300  # 5 minutes

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

_FUTURES_KLINES = "https://fapi.binance.com/fapi/v1/klines"
_SPOT_KLINES = "https://data-api.binance.vision/api/v3/klines"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def _fetch_sync(url: str) -> list | None:
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


async def get_ohlcv(symbol: str, interval: str = "1h", limit: int = 210) -> list:
    """Return [[ts, open, high, low, close, volume], ...]. Cached 5 min."""
    key = f"{symbol}_{interval}"
    if key in _cache and time.time() - _cache_ts.get(key, 0) < CACHE_TTL:
        return _cache[key]

    binance_sym = SYMBOL_MAP.get(symbol, symbol.replace("/", ""))
    loop = asyncio.get_event_loop()
    raw = None
    for base_url in (_SPOT_KLINES, _FUTURES_KLINES):
        url = f"{base_url}?symbol={binance_sym}&interval={interval}&limit={limit}"
        raw = await loop.run_in_executor(None, _fetch_sync, url)
        if raw:
            break

    if not raw:
        print(f"[market_data] {symbol} both endpoints failed")
        return _cache.get(key, [])

    data = [
        [int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])]
        for r in raw
    ]
    _cache[key] = data
    _cache_ts[key] = time.time()
    print(f"[market_data] {symbol} fetched {len(data)} candles")
    return data


async def get_ohlcv_multi(symbols: list, interval: str = "1h") -> dict:
    """Fetch multiple symbols concurrently."""
    results = await asyncio.gather(
        *[get_ohlcv(s, interval) for s in symbols], return_exceptions=True
    )
    return {sym: (r if isinstance(r, list) else []) for sym, r in zip(symbols, results)}
