import glob

import numpy as np
import pandas as pd

SWING_N = 3
OB_LOOKBACK = 10
SWEEP_LOOKBACK = 60
SWEEP_RECLAIM_BARS = 3
DISPLACEMENT_MULT = 1.5
ORDER_EXPIRY_BARS = 36
MIN_STOP_PCT = 0.002
ATR_STOP_MULT = 0.3
RR = 2.0
FIB_LOW = 0.618
FIB_HIGH = 0.705


def load_candles(pattern):
    frames = []
    for path in sorted(glob.glob(pattern)):
        frames.append(pd.read_csv(path, header=None, usecols=range(6),
                                  names=["ts", "open", "high", "low", "close", "volume"]))
    df = pd.concat(frames)
    ts = df["ts"].astype("int64").to_numpy()
    ts = np.where(ts > 10**14, ts // 1000, ts)
    df["time"] = pd.to_datetime(ts, unit="ms", utc=True)
    return df.drop(columns="ts").drop_duplicates("time").set_index("time").sort_index()


def hourly_trend(df, rule="1h"):
    h1 = df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    ema = h1["close"].ewm(span=200, adjust=False).mean().to_numpy()
    hi, lo, cl = h1["high"].to_numpy(), h1["low"].to_numpy(), h1["close"].to_numpy()
    state = np.zeros(len(h1), dtype=int)
    swing_high = swing_low = None
    current = 0
    for i in range(len(h1)):
        c = i - SWING_N
        if c >= SWING_N:
            if hi[c] > hi[c - SWING_N:c].max() and hi[c] > hi[c + 1:i + 1].max():
                swing_high = hi[c]
            if lo[c] < lo[c - SWING_N:c].min() and lo[c] < lo[c + 1:i + 1].min():
                swing_low = lo[c]
        if swing_high is not None and cl[i] > swing_high:
            current, swing_high = 1, None
        if swing_low is not None and cl[i] < swing_low:
            current, swing_low = -1, None
        state[i] = current
    trend = np.where((state == 1) & (cl > ema), 1, np.where((state == -1) & (cl < ema), -1, 0))
    available_at = pd.Series(trend, index=h1.index + pd.Timedelta(rule))
    return available_at.reindex(df.index, method="ffill").fillna(0).astype(int).to_numpy()


def find_setups(df, require_sweep=True, use_fib=True, trend_rule="1h"):
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    n = len(df)
    prev_close = np.roll(c, 1)
    prev_close[0] = c[0]
    tr = np.maximum(h - l, np.maximum(abs(h - prev_close), abs(l - prev_close)))
    atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    body = abs(c - o)
    avg_body = pd.Series(body).rolling(20).mean().shift(1).to_numpy()
    trend = hourly_trend(df, trend_rule)

    swing_highs, swing_lows = [], []
    last_high = last_low = None
    pending = None
    position = None
    trades = []

    def latest_swing_before(swings, bar):
        for idx, price in reversed(swings):
            if idx + SWING_N <= bar:
                return (idx, price) if idx >= bar - SWEEP_LOOKBACK else None
        return None

    def build_long(i):
        start = last_high[0]
        low_idx = start + int(np.argmin(l[start:i + 1]))
        ob = next((k for k in range(low_idx, max(start, low_idx - OB_LOOKBACK) - 1, -1) if c[k] < o[k]), None)
        if ob is None:
            return None
        if not any(body[k] > DISPLACEMENT_MULT * avg_body[k] for k in range(ob + 1, i + 1) if not np.isnan(avg_body[k])):
            return None
        fvg = next(((k, h[k], l[k + 2]) for k in range(ob, i - 1) if l[k + 2] > h[k] and h[k] <= h[ob]), None)
        if fvg is None:
            return None
        k, fvg_bottom, fvg_top = fvg
        if k + 3 <= i and l[k + 3:i + 1].min() <= fvg_top:
            return None
        sweep = latest_swing_before(swing_lows, low_idx)
        swept = sweep is not None and l[low_idx] < sweep[1] and c[low_idx:min(low_idx + SWEEP_RECLAIM_BARS, i + 1)].max() > sweep[1]
        if require_sweep and not swept:
            return None
        stop = min(l[ob], l[low_idx]) - ATR_STOP_MULT * atr[i]
        hi_idx = low_idx + int(np.argmax(h[low_idx:i + 1]))
        return dict(side="long", bos_idx=i, bos_level=last_high, ob_idx=ob, fvg_idx=k,
                    fvg=(fvg_bottom, fvg_top), anchor_idx=low_idx, anchor=l[low_idx],
                    extreme_idx=hi_idx, extreme=h[hi_idx], stop=stop, invalidation=min(l[ob], l[low_idx]),
                    sweep=sweep if swept else None)

    def build_short(i):
        start = last_low[0]
        high_idx = start + int(np.argmax(h[start:i + 1]))
        ob = next((k for k in range(high_idx, max(start, high_idx - OB_LOOKBACK) - 1, -1) if c[k] > o[k]), None)
        if ob is None:
            return None
        if not any(body[k] > DISPLACEMENT_MULT * avg_body[k] for k in range(ob + 1, i + 1) if not np.isnan(avg_body[k])):
            return None
        fvg = next(((k, h[k + 2], l[k]) for k in range(ob, i - 1) if h[k + 2] < l[k] and l[k] >= l[ob]), None)
        if fvg is None:
            return None
        k, fvg_bottom, fvg_top = fvg
        if k + 3 <= i and h[k + 3:i + 1].max() >= fvg_bottom:
            return None
        sweep = latest_swing_before(swing_highs, high_idx)
        swept = sweep is not None and h[high_idx] > sweep[1] and c[high_idx:min(high_idx + SWEEP_RECLAIM_BARS, i + 1)].min() < sweep[1]
        if require_sweep and not swept:
            return None
        stop = max(h[ob], h[high_idx]) + ATR_STOP_MULT * atr[i]
        lo_idx = high_idx + int(np.argmin(l[high_idx:i + 1]))
        return dict(side="short", bos_idx=i, bos_level=last_low, ob_idx=ob, fvg_idx=k,
                    fvg=(fvg_bottom, fvg_top), anchor_idx=high_idx, anchor=h[high_idx],
                    extreme_idx=lo_idx, extreme=l[lo_idx], stop=stop, invalidation=max(h[ob], h[high_idx]),
                    sweep=sweep if swept else None)

    def order_price(p):
        rng = abs(p["extreme"] - p["anchor"])
        bottom, top = p["fvg"]
        if p["side"] == "long":
            price = top
            if use_fib:
                fib_top, fib_bottom = p["extreme"] - FIB_LOW * rng, p["extreme"] - FIB_HIGH * rng
                price = min(top, fib_top)
                if price < max(bottom, fib_bottom):
                    return None
            return price if (price - p["stop"]) / price >= MIN_STOP_PCT else None
        price = bottom
        if use_fib:
            fib_bottom, fib_top = p["extreme"] + FIB_LOW * rng, p["extreme"] + FIB_HIGH * rng
            price = max(bottom, fib_bottom)
            if price > min(top, fib_top):
                return None
        return price if (p["stop"] - price) / price >= MIN_STOP_PCT else None

    def close_trade(pos, i, price, reason):
        pos.update(exit_idx=i, exit_price=price, exit_reason=reason)
        risk = abs(pos["entry"] - pos["stop"])
        sign = 1 if pos["side"] == "long" else -1
        pos["r"] = sign * (price - pos["entry"]) / risk
        trades.append(pos)

    for i in range(n):
        if position is not None:
            p = position
            if p["side"] == "long":
                if l[i] <= p["stop"]:
                    close_trade(p, i, min(o[i], p["stop"]), "stop")
                    position = None
                elif h[i] >= p["tp"]:
                    close_trade(p, i, p["tp"], "tp")
                    position = None
            else:
                if h[i] >= p["stop"]:
                    close_trade(p, i, max(o[i], p["stop"]), "stop")
                    position = None
                elif l[i] <= p["tp"]:
                    close_trade(p, i, p["tp"], "tp")
                    position = None
        elif pending is not None:
            p = pending
            price = order_price(p)
            long_side = p["side"] == "long"
            touched_fvg = l[i] <= p["fvg"][1] if long_side else h[i] >= p["fvg"][0]
            if i > p["bos_idx"] + ORDER_EXPIRY_BARS:
                pending = None
            elif price is not None and ((long_side and l[i] <= price) or (not long_side and h[i] >= price)):
                entry = min(price, o[i]) if long_side else max(price, o[i])
                risk = abs(entry - p["stop"])
                trade = dict(p, entry_idx=i, entry=entry, order_price=price,
                             tp=entry + RR * risk if long_side else entry - RR * risk,
                             fib_range=(p["anchor"], p["extreme"]))
                pending = None
                if (long_side and l[i] <= trade["stop"]) or (not long_side and h[i] >= trade["stop"]):
                    close_trade(trade, i, trade["stop"], "stop")
                else:
                    position = trade
            elif price is None and touched_fvg:
                pending = None
            elif (long_side and c[i] < p["invalidation"]) or (not long_side and c[i] > p["invalidation"]):
                pending = None
            elif long_side and h[i] > p["extreme"]:
                p["extreme"], p["extreme_idx"] = h[i], i
            elif not long_side and l[i] < p["extreme"]:
                p["extreme"], p["extreme_idx"] = l[i], i

        cand = i - SWING_N
        if cand >= SWING_N:
            if h[cand] > h[cand - SWING_N:cand].max() and h[cand] > h[cand + 1:i + 1].max():
                swing_highs.append((cand, h[cand]))
                last_high = (cand, h[cand])
            if l[cand] < l[cand - SWING_N:cand].min() and l[cand] < l[cand + 1:i + 1].min():
                swing_lows.append((cand, l[cand]))
                last_low = (cand, l[cand])

        if last_high is not None and c[i] > last_high[1]:
            setup = build_long(i) if position is None and trend[i] == 1 else None
            last_high = None
            if setup:
                pending = setup
        if last_low is not None and c[i] < last_low[1]:
            setup = build_short(i) if position is None and trend[i] == -1 else None
            last_low = None
            if setup:
                pending = setup

    return trades
