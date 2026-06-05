"""Pure-numpy technical indicators — no external TA libs needed."""

from typing import List, Tuple


def ema(data: List[float], period: int) -> List[float]:
    k = 2.0 / (period + 1)
    result = [data[0]]
    for p in data[1:]:
        result.append(p * k + result[-1] * (1 - k))
    return result


def sma(data: List[float], period: int) -> float:
    return sum(data[-period:]) / min(len(data), period)


def rsi(data: List[float], period: int = 14) -> float:
    if len(data) < period + 1:
        return 50.0
    changes = [data[i] - data[i - 1] for i in range(1, len(data))]
    gains = [max(c, 0.0) for c in changes[-period:]]
    losses = [abs(min(c, 0.0)) for c in changes[-period:]]
    avg_g = sum(gains) / period
    avg_l = sum(losses) / period
    if avg_l == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_g / avg_l), 2)


def macd(
    data: List[float], fast: int = 12, slow: int = 26, sig: int = 9
) -> Tuple[float, float, float]:
    if len(data) < slow + sig:
        return 0.0, 0.0, 0.0
    e_fast = ema(data, fast)
    e_slow = ema(data, slow)
    macd_line = [f - s for f, s in zip(e_fast, e_slow)]
    sig_line = ema(macd_line, sig)
    hist = macd_line[-1] - sig_line[-1]
    return macd_line[-1], sig_line[-1], hist


def atr(ohlcv: list, period: int = 14) -> float:
    tr_vals = []
    for i in range(1, len(ohlcv)):
        h, l_, pc = ohlcv[i][2], ohlcv[i][3], ohlcv[i - 1][4]
        tr_vals.append(max(h - l_, abs(h - pc), abs(l_ - pc)))
    if not tr_vals:
        return 0.0
    return sum(tr_vals[-period:]) / min(len(tr_vals), period)


def bollinger(
    data: List[float], period: int = 20, mult: float = 2.0
) -> Tuple[float, float, float]:
    if len(data) < period:
        return data[-1] * 1.02, data[-1], data[-1] * 0.98
    w = data[-period:]
    mid = sum(w) / period
    std = (sum((x - mid) ** 2 for x in w) / period) ** 0.5
    return mid + mult * std, mid, mid - mult * std


def swing_highs_lows(
    prices: List[float], lb: int = 5
) -> Tuple[List[float], List[float]]:
    highs, lows = [], []
    for i in range(lb, len(prices) - lb):
        if all(
            prices[i] >= prices[i - j] and prices[i] >= prices[i + j]
            for j in range(1, lb + 1)
        ):
            highs.append(prices[i])
        if all(
            prices[i] <= prices[i - j] and prices[i] <= prices[i + j]
            for j in range(1, lb + 1)
        ):
            lows.append(prices[i])
    return highs, lows


def volume_profile(ohlcv: list, bins: int = 24) -> Tuple[float, float, float]:
    """Returns (POC, VAH, VAL) using simplified volume distribution."""
    lo = min(c[3] for c in ohlcv)
    hi = max(c[2] for c in ohlcv)
    if hi == lo:
        return hi, hi, lo
    size = (hi - lo) / bins
    vol_bins = [0.0] * bins
    for c in ohlcv:
        mid = (c[2] + c[3]) / 2
        idx = min(int((mid - lo) / size), bins - 1)
        vol_bins[idx] += c[5]

    poc_idx = vol_bins.index(max(vol_bins))
    poc = lo + (poc_idx + 0.5) * size

    total = sum(vol_bins)
    ranked = sorted(range(bins), key=lambda i: vol_bins[i], reverse=True)
    va_bins, cum = set(), 0.0
    for idx in ranked:
        va_bins.add(idx)
        cum += vol_bins[idx]
        if cum >= 0.7 * total:
            break

    vah = lo + (max(va_bins) + 1) * size
    val_ = lo + min(va_bins) * size
    return poc, vah, val_


def find_fvg(ohlcv: list) -> Tuple[list, list]:
    """Fair Value Gaps: bullish (price gaps up) and bearish (price gaps down)."""
    bull_fvg, bear_fvg = [], []
    for i in range(1, len(ohlcv) - 1):
        if ohlcv[i - 1][2] < ohlcv[i + 1][3]:  # bullish gap
            bull_fvg.append((ohlcv[i - 1][2], ohlcv[i + 1][3]))
        if ohlcv[i - 1][3] > ohlcv[i + 1][2]:  # bearish gap
            bear_fvg.append((ohlcv[i + 1][2], ohlcv[i - 1][3]))
    return bull_fvg, bear_fvg


def adx(ohlcv: list, period: int = 14) -> float:
    """Average Directional Index — measures trend strength (not direction).
    > 25: trending market (trade)
    < 20: choppy / sideways (avoid)
    """
    if len(ohlcv) < period * 2:
        return 25.0  # assume neutral if insufficient data
    tr_vals, plus_dm, minus_dm = [], [], []
    for i in range(1, len(ohlcv)):
        h, l_, ph, pl = ohlcv[i][2], ohlcv[i][3], ohlcv[i-1][2], ohlcv[i-1][3]
        pc = ohlcv[i-1][4]
        tr_vals.append(max(h - l_, abs(h - pc), abs(l_ - pc)))
        up, dn = h - ph, pl - l_
        plus_dm.append(up if up > dn and up > 0 else 0.0)
        minus_dm.append(dn if dn > up and dn > 0 else 0.0)

    def _smooth(vals: list) -> list:
        out = [sum(vals[:period])]
        for v in vals[period:]:
            out.append(out[-1] - out[-1] / period + v)
        return out

    atr_s = _smooth(tr_vals)
    pdm_s = _smooth(plus_dm)
    mdm_s = _smooth(minus_dm)

    dx_vals = []
    for a, p, m in zip(atr_s, pdm_s, mdm_s):
        if a == 0:
            continue
        pdi = 100 * p / a
        mdi = 100 * m / a
        denom = pdi + mdi
        dx_vals.append(100 * abs(pdi - mdi) / denom if denom > 0 else 0.0)

    if not dx_vals:
        return 25.0
    adx_val = sum(dx_vals[-period:]) / min(len(dx_vals), period)
    return round(adx_val, 2)


def volume_delta_proxy(ohlcv: list, period: int = 20) -> float:
    """Proxy for CVD: positive = net buying, negative = net selling."""
    delta = 0.0
    for c in ohlcv[-period:]:
        body = c[4] - c[1]  # close - open
        vol = c[5]
        delta += vol if body > 0 else -vol if body < 0 else 0
    return delta


def vwap_bands(ohlcv: list, period: int = 24) -> Tuple[float, float, float]:
    """Rolling VWAP with ±2σ price-weighted bands. Returns (vwap, upper, lower)."""
    recent = ohlcv[-period:]
    cum_vol, cum_pv = 0.0, 0.0
    prices = []
    for c in recent:
        tp = (c[2] + c[3] + c[4]) / 3
        cum_pv += tp * c[5]
        cum_vol += c[5]
        prices.append(tp)
    vwap_val = cum_pv / cum_vol if cum_vol > 0 else prices[-1]
    variance = sum((p - vwap_val) ** 2 for p in prices) / len(prices)
    std = variance ** 0.5
    return vwap_val, vwap_val + 2 * std, vwap_val - 2 * std


def supertrend(ohlcv: list, period: int = 10, mult: float = 3.0) -> Tuple[List[float], List[int]]:
    """SuperTrend indicator. Returns (st_line, directions) direction: 1=bullish -1=bearish."""
    n = len(ohlcv)
    if n < period + 2:
        return [], []
    tr_vals = [max(ohlcv[i][2] - ohlcv[i][3],
                   abs(ohlcv[i][2] - ohlcv[i-1][4]),
                   abs(ohlcv[i][3] - ohlcv[i-1][4])) for i in range(1, n)]
    atr_s = sum(tr_vals[:period]) / period
    atr_smooth = [atr_s]
    for v in tr_vals[period:]:
        atr_s = (atr_s * (period - 1) + v) / period
        atr_smooth.append(atr_s)

    st_line, directions = [], []
    up = True
    fl, fu = 0.0, float("inf")
    for j, atr_v in enumerate(atr_smooth):
        i = j + period
        if i >= n:
            break
        c = ohlcv[i]
        hl2 = (c[2] + c[3]) / 2
        bu, bl = hl2 + mult * atr_v, hl2 - mult * atr_v
        if j == 0:
            fu, fl = bu, bl
        else:
            prev_close = ohlcv[i - 1][4]
            fu = min(bu, fu) if prev_close <= fu else bu
            fl = max(bl, fl) if prev_close >= fl else bl
        if c[4] > fu:
            up = True
        elif c[4] < fl:
            up = False
        directions.append(1 if up else -1)
        st_line.append(fl if up else fu)
    return st_line, directions


def fvg_recent(ohlcv: list, lookback: int = 30) -> Tuple[list, list]:
    """Fair Value Gaps in the last `lookback` bars.
    Bullish FVG: candle[i-1].high < candle[i+1].low (gap up — price may return to fill).
    Bearish FVG: candle[i-1].low > candle[i+1].high (gap down).
    Returns (bull_fvgs, bear_fvgs) each as list of (low, high) tuples."""
    recent = ohlcv[-lookback:] if len(ohlcv) >= lookback else ohlcv
    bull, bear = [], []
    for i in range(1, len(recent) - 1):
        gap_lo = recent[i - 1][2]  # prev high
        gap_hi = recent[i + 1][3]  # next low
        if gap_hi > gap_lo:        # bullish gap: price moved up, left void below
            bull.append((gap_lo, gap_hi))
        gap_lo2 = recent[i + 1][2]  # next high
        gap_hi2 = recent[i - 1][3]  # prev low
        if gap_hi2 < gap_lo2:       # bearish gap: price moved down, left void above
            bear.append((gap_lo2, gap_hi2))
    return bull, bear


def candle_hour_utc(ohlcv_bar: list) -> int:
    """Extract UTC hour from a Binance OHLCV bar (timestamp in ms)."""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ohlcv_bar[0] / 1000, tz=timezone.utc).hour


def keltner(ohlcv: list, period: int = 20, mult: float = 1.5) -> Tuple[float, float, float]:
    """Keltner Channel (EMA ± mult×ATR). Returns (upper, mid, lower)."""
    closes = [c[4] for c in ohlcv]
    mid = ema(closes, period)[-1]
    atr_val = atr(ohlcv, period)
    return mid + mult * atr_val, mid, mid - mult * atr_val


def momentum_score(closes: List[float], lookbacks: Tuple = (24, 72, 168)) -> float:
    """Average normalised momentum across multiple lookback windows. Range ≈ -1 to +1."""
    scores = []
    for lb in lookbacks:
        if len(closes) > lb:
            ret = (closes[-1] - closes[-lb]) / closes[-lb]
            scores.append(ret)
    return sum(scores) / len(scores) if scores else 0.0
