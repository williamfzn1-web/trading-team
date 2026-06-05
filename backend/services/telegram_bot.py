"""Telegram push notifications for trade events."""

import asyncio
import json
import os
import urllib.request

_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def _send_sync(text: str) -> None:
    if not _TOKEN or not _CHAT_ID:
        return
    payload = json.dumps(
        {"chat_id": _CHAT_ID, "text": text, "parse_mode": "HTML"}
    ).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{_TOKEN}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception as e:
        print(f"[telegram] send error: {e}")


async def send(text: str) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _send_sync, text)


async def notify_open(
    analyst_name: str,
    strategy: str,
    symbol: str,
    side: str,
    price: float,
    sl: float,
    tp: float,
    quantity: float,
    reason: str,
) -> None:
    icon = "🟢" if side == "long" else "🔴"
    direction = "LONG" if side == "long" else "SHORT"
    await send(
        f"{icon} <b>OPEN {direction}</b>  {symbol}\n"
        f"分析師：{analyst_name}（{strategy}）\n"
        f"進場：<b>${price:,.2f}</b>\n"
        f"SL：${sl:,.2f}  |  TP：${tp:,.2f}\n"
        f"倉位：${quantity:,.0f}\n"
        f"📋 {reason}"
    )


async def notify_close(
    analyst_name: str,
    strategy: str,
    symbol: str,
    side: str,
    entry: float,
    exit_price: float,
    pnl: float,
) -> None:
    pnl_pct = pnl / (entry if entry else 1) * 100
    icon = "✅" if pnl >= 0 else "❌"
    sign = "+" if pnl >= 0 else ""
    direction = "LONG" if side == "long" else "SHORT"
    await send(
        f"{icon} <b>CLOSE {direction}</b>  {symbol}\n"
        f"分析師：{analyst_name}（{strategy}）\n"
        f"進場 ${entry:,.2f} → 出場 ${exit_price:,.2f}\n"
        f"PnL：<b>{sign}${pnl:,.2f}</b>（{sign}{pnl_pct:.2f}%）"
    )
