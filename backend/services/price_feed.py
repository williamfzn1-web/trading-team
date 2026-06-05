import asyncio
import json
from typing import Callable, Set
from fastapi import WebSocket
from services.exchange import fetch_prices

_prices: dict = {}
_connections: Set[WebSocket] = set()


def get_current_prices() -> dict:
    return _prices


def add_connection(ws: WebSocket):
    _connections.add(ws)


def remove_connection(ws: WebSocket):
    _connections.discard(ws)


async def broadcast(data: dict):
    global _connections
    dead = set()
    for ws in _connections.copy():
        try:
            await ws.send_text(json.dumps(data))
        except Exception:
            dead.add(ws)
    _connections = _connections - dead


async def price_feed_loop(get_account_data: Callable):
    global _prices
    while True:
        try:
            fresh = await fetch_prices()
            if fresh:
                _prices = fresh
            account_data = await get_account_data(_prices)
            await broadcast(
                {"type": "update", "prices": _prices, "accounts": account_data}
            )
        except Exception as e:
            print(f"[price_feed] error: {e}")
        await asyncio.sleep(5)
