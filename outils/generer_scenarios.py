"""Génère scenarios.js à partir des bougies 5 min BTC/USDC de Binance.

Usage :
    python3 outils/telecharger_bougies.py 2024-11 2026-10
    python3 outils/generer_scenarios.py
"""
import json
import random
from pathlib import Path

import numpy as np

import smc

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "outils" / "donnees" / "*.csv"
OUTPUT = ROOT / "scenarios.js"

BARS_BEFORE_MIN = 70
BARS_BEFORE_MAX = 130
BARS_AFTER = 144
H1_BARS = 48
MIN_RISK_PCT = 0.0015
SEED = 7


def collect_setups(df):
    unique = {}
    for require_sweep in (True, False):
        for use_fib in (True, False):
            for trade in smc.find_setups(df, require_sweep=require_sweep, use_fib=use_fib):
                trade["has_sweep"] = trade["sweep"] is not None
                trade["has_fib"] = use_fib
                unique.setdefault(trade["entry_idx"], trade)
    return sorted(unique.values(), key=lambda t: t["entry_idx"])


def usable(trade, close):
    decision = trade["entry_idx"]
    price = close[decision]
    if trade["exit_idx"] == decision:
        return False
    risk = price - trade["stop"] if trade["side"] == "long" else trade["stop"] - price
    return risk / price >= MIN_RISK_PCT


def build_scenario(df, h1, trade):
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    decision = trade["entry_idx"]
    anchors = [trade["bos_level"][0], trade["ob_idx"], trade["anchor_idx"]]
    if trade["sweep"]:
        anchors.append(trade["sweep"][0])
    start = max(0, min(decision - BARS_BEFORE_MIN, min(anchors) - 20))
    start = max(start, decision - BARS_BEFORE_MAX)
    end = min(len(df), decision + BARS_AFTER + 1)
    base = int(round(o[start]))
    candles = [[int(round(v - base)) for v in (o[i], h[i], l[i], c[i])] for i in range(start, end)]

    decision_close_time = df.index[decision] + np.timedelta64(5, "m")
    done_h1 = h1[h1.index + np.timedelta64(1, "h") <= decision_close_time].tail(H1_BARS)
    hourly = [[int(round(v - base)) for v in (r.open, r.high, r.low, r.close)] for r in done_h1.itertuples()]

    rel = lambda idx: int(idx - start)
    price = c[decision]
    risk = price - trade["stop"] if trade["side"] == "long" else trade["stop"] - price
    anchor, extreme = trade["fib_range"]
    annotations = {
        "bos": [rel(trade["bos_level"][0]), rel(trade["bos_idx"]), round(trade["bos_level"][1], 1)],
        "ob": [rel(trade["ob_idx"]), round(l[trade["ob_idx"]], 1), round(h[trade["ob_idx"]], 1)],
        "fvg": [rel(trade["fvg_idx"]), round(trade["fvg"][0], 1), round(trade["fvg"][1], 1)],
        "fib": [rel(trade["anchor_idx"]), rel(trade["extreme_idx"]), round(anchor, 1), round(extreme, 1)],
        "stop": round(trade["stop"], 1),
    }
    if trade["sweep"]:
        annotations["liq"] = [rel(trade["sweep"][0]), rel(trade["anchor_idx"]), round(trade["sweep"][1], 1)]
    return {
        "t": int(df.index[start].timestamp()),
        "b": base,
        "c": candles,
        "d": rel(decision),
        "h1": hourly,
        "h1t": int(done_h1.index[0].timestamp()) if len(done_h1) else 0,
        "side": "buy" if trade["side"] == "long" else "sell",
        "risk": round(float(risk), 1),
        "a": annotations,
        "sweep": trade["has_sweep"],
        "fibOk": trade["has_fib"],
    }


def main():
    df = smc.load_candles(str(RAW))
    h1 = df.resample("1h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    close = df["close"].to_numpy()
    trades = [t for t in collect_setups(df) if usable(t, close)]
    scenarios = [build_scenario(df, h1, t) for t in trades]
    random.Random(SEED).shuffle(scenarios)
    for number, scenario in enumerate(scenarios, 1):
        scenario["id"] = number
    payload = json.dumps(scenarios, separators=(",", ":"))
    OUTPUT.write_text(f"window.SCENARIOS={payload};\n", encoding="utf-8")
    buys = sum(s["side"] == "buy" for s in scenarios)
    print(f"{len(scenarios)} scénarios ({buys} achats, {len(scenarios) - buys} ventes) -> {OUTPUT}")


if __name__ == "__main__":
    main()
