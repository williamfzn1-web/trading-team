import asyncio
import json
import urllib.request

SYMBOL_MAP = {
    "BTCUSDT": "BTC/USDT",
    "ETHUSDT": "ETH/USDT",
    "SOLUSDT": "SOL/USDT",
    "BNBUSDT": "BNB/USDT",
    "XRPUSDT": "XRP/USDT",
    "ADAUSDT": "ADA/USDT",
    "AVAXUSDT": "AVAX/USDT",
    "DOTUSDT": "DOT/USDT",
    "LINKUSDT": "LINK/USDT",
    "MATICUSDT": "MATIC/USDT",
}

_fallback_prices = {
    "BTC/USDT": {
        "price": 67000.0,
        "change_24h": 1.2,
        "volume_24h": 2800000000,
        "high_24h": 68000.0,
        "low_24h": 66000.0,
    },
    "ETH/USDT": {
        "price": 3500.0,
        "change_24h": 0.8,
        "volume_24h": 900000000,
        "high_24h": 3600.0,
        "low_24h": 3450.0,
    },
    "SOL/USDT": {
        "price": 175.0,
        "change_24h": 2.1,
        "volume_24h": 400000000,
        "high_24h": 180.0,
        "low_24h": 170.0,
    },
    "BNB/USDT": {
        "price": 600.0,
        "change_24h": 0.5,
        "volume_24h": 250000000,
        "high_24h": 610.0,
        "low_24h": 595.0,
    },
    "XRP/USDT": {
        "price": 0.52,
        "change_24h": -0.3,
        "volume_24h": 180000000,
        "high_24h": 0.54,
        "low_24h": 0.51,
    },
    "ADA/USDT": {
        "price": 0.45,
        "change_24h": 1.0,
        "volume_24h": 120000000,
        "high_24h": 0.46,
        "low_24h": 0.44,
    },
    "AVAX/USDT": {
        "price": 38.0,
        "change_24h": 1.5,
        "volume_24h": 150000000,
        "high_24h": 39.0,
        "low_24h": 37.0,
    },
    "DOT/USDT": {
        "price": 7.2,
        "change_24h": 0.2,
        "volume_24h": 80000000,
        "high_24h": 7.4,
        "low_24h": 7.1,
    },
    "LINK/USDT": {
        "price": 14.5,
        "change_24h": 1.8,
        "volume_24h": 90000000,
        "high_24h": 15.0,
        "low_24h": 14.2,
    },
    "MATIC/USDT": {
        "price": 0.72,
        "change_24h": -0.5,
        "volume_24h": 100000000,
        "high_24h": 0.74,
        "low_24h": 0.71,
    },
}

_BYBIT_MAP = {
    "BTCUSDT": "BTC/USDT",
    "ETHUSDT": "ETH/USDT",
    "SOLUSDT": "SOL/USDT",
    "BNBUSDT": "BNB/USDT",
    "XRPUSDT": "XRP/USDT",
    "ADAUSDT": "ADA/USDT",
    "AVAXUSDT": "AVAX/USDT",
    "DOTUSDT": "DOT/USDT",
    "LINKUSDT": "LINK/USDT",
    "MATICUSDT": "MATIC/USDT",
}

_GECKO_IDS = "bitcoin,ethereum,solana,binancecoin,ripple,cardano,avalanche-2,polkadot,chainlink,matic-network"
_GECKO_ID_MAP = {
    "bitcoin": "BTC/USDT",
    "ethereum": "ETH/USDT",
    "solana": "SOL/USDT",
    "binancecoin": "BNB/USDT",
    "ripple": "XRP/USDT",
    "cardano": "ADA/USDT",
    "avalanche-2": "AVAX/USDT",
    "polkadot": "DOT/USDT",
    "chainlink": "LINK/USDT",
    "matic-network": "MATIC/USDT",
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def _http_get(url: str):
    """Synchronous urllib GET — proven to bypass any aiohttp blocking."""
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        raise e


async def _fetch(url: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _http_get, url)


async def _try_bybit() -> dict:
    url = "https://api.bybit.com/v5/market/tickers?category=linear"
    data = (await _fetch(url)).get("result", {}).get("list", [])
    return {
        _BYBIT_MAP[t["symbol"]]: {
            "price": float(t["lastPrice"]),
            "change_24h": float(t["price24hPcnt"]) * 100,
            "volume_24h": float(t.get("turnover24h", 0)),
            "high_24h": float(t["highPrice24h"]),
            "low_24h": float(t["lowPrice24h"]),
        }
        for t in data
        if t["symbol"] in _BYBIT_MAP
    }


async def _try_binance(label: str, url: str) -> dict:
    data = await _fetch(url)
    return {
        SYMBOL_MAP[t["symbol"]]: {
            "price": float(t["lastPrice"]),
            "change_24h": float(t["priceChangePercent"]),
            "volume_24h": float(t["quoteVolume"]),
            "high_24h": float(t["highPrice"]),
            "low_24h": float(t["lowPrice"]),
        }
        for t in data
        if t["symbol"] in SYMBOL_MAP
    }


async def _try_coingecko() -> dict:
    url = (
        f"https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency=usd&ids={_GECKO_IDS}&per_page=20&sparkline=false"
    )
    data = await _fetch(url)
    return {
        _GECKO_ID_MAP[c["id"]]: {
            "price": float(c["current_price"]),
            "change_24h": float(c.get("price_change_percentage_24h") or 0),
            "volume_24h": float(c.get("total_volume") or 0),
            "high_24h": float(c.get("high_24h") or 0),
            "low_24h": float(c.get("low_24h") or 0),
        }
        for c in data
        if c["id"] in _GECKO_ID_MAP
    }


async def fetch_prices() -> dict:
    sources = [
        (
            "futures",
            lambda: _try_binance(
                "futures", "https://fapi.binance.com/fapi/v1/ticker/24hr"
            ),
        ),
        ("bybit", _try_bybit),
        (
            "spot-mirror",
            lambda: _try_binance(
                "spot-mirror", "https://data-api.binance.vision/api/v3/ticker/24hr"
            ),
        ),
        ("coingecko", _try_coingecko),
    ]
    for label, fn in sources:
        try:
            result = await fn()
            if result:
                print(f"[price] {label} OK ({len(result)} symbols)")
                return result
            print(f"[price] {label} empty result")
        except Exception as e:
            print(f"[price] {label} error: {type(e).__name__}: {e}")
    print("[price] all sources failed, using fallback")
    return _fallback_prices
