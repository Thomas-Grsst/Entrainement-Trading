"""Génère scenarios.js : situations réelles XAUUSD, EURUSD et GBPUSD en 15 min.

Usage :
    python3 outils/telecharger_donnees.py
    python3 outils/generer_scenarios.py
"""
import glob
import json
import random
from pathlib import Path

import pandas as pd

import smc

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "outils" / "donnees" / "fx"
OUTPUT = ROOT / "scenarios.js"

PAIRS = {"XAUUSD": 2, "EURUSD": 5, "GBPUSD": 5}
START = pd.Timestamp("2024-02-01", tz="UTC")
END = pd.Timestamp("2026-11-01", tz="UTC")
TREND = "4h"
STEP_SECONDS = 900
BARS_BEFORE_MIN = 70
BARS_BEFORE_MAX = 130
BARS_AFTER = 144
HTF_BARS = 48
CONFIRM_BARS = 6
MIN_RISK_PCT = 0.0005
SEED = 11


def load_pair(pair):
    frames = [pd.read_csv(path, sep=";", header=None, names=["ts", "open", "high", "low", "close", "volume"])
              for path in sorted(glob.glob(str(DATA / pair / "*.csv")))]
    df = pd.concat(frames)
    df["time"] = pd.to_datetime(df["ts"], format="%Y%m%d %H%M%S").dt.tz_localize("Etc/GMT+5").dt.tz_convert("UTC")
    df = df.drop(columns="ts").drop_duplicates("time").set_index("time").sort_index()
    df = df[df.index < END]
    return df.resample("15min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()


def reversal_bar(o, h, l, c, trade):
    side, stop = trade["side"], trade["stop"]
    for i in range(trade["entry_idx"], min(len(c), trade["entry_idx"] + CONFIRM_BARS + 1)):
        if (side == "long" and l[i] <= stop) or (side == "short" and h[i] >= stop):
            return None
        if side == "long" and c[i] > h[i - 1]:
            return i
        if side == "short" and c[i] < l[i - 1]:
            return i
    return None


def collect(df):
    unique = {}
    for require_sweep in (True, False):
        for use_fib in (True, False):
            for trade in smc.find_setups(df, require_sweep=require_sweep, use_fib=use_fib, trend_rule=TREND):
                trade["has_fib"] = use_fib
                unique.setdefault(trade["entry_idx"], trade)
    return sorted(unique.values(), key=lambda t: t["entry_idx"])


def higher_timeframe(df, rule, decision_close):
    bars = df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    done = bars[bars.index + pd.Timedelta(rule) <= decision_close].tail(HTF_BARS)
    return done


def build(df, pair, decimals, trade, decision):
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    scale = 10 ** decimals
    anchors = [trade["bos_level"][0], trade["ob_idx"], trade["anchor_idx"]]
    if trade["sweep"]:
        anchors.append(trade["sweep"][0])
    start = max(0, min(decision - BARS_BEFORE_MIN, min(anchors) - 20))
    start = max(start, decision - BARS_BEFORE_MAX)
    end = min(len(df), decision + BARS_AFTER + 1)
    base = int(round(o[start] * scale))
    to_points = lambda value: int(round(value * scale)) - base
    candles = [[to_points(v) for v in (o[i], h[i], l[i], c[i])] for i in range(start, end)]

    decision_close = df.index[decision] + pd.Timedelta(seconds=STEP_SECONDS)
    htf = {}
    for key, rule in (("h1", "1h"), ("h4", "4h")):
        bars = higher_timeframe(df.iloc[max(0, start - 1200):decision + 1], rule, decision_close)
        htf[key] = {
            "t": int(bars.index[0].timestamp()) if len(bars) else 0,
            "c": [[to_points(v) for v in (r.open, r.high, r.low, r.close)] for r in bars.itertuples()],
        }

    rel = lambda idx: int(idx - start)
    price = c[decision]
    risk = price - trade["stop"] if trade["side"] == "long" else trade["stop"] - price
    rnd = lambda value: round(float(value), decimals + 1)
    anchor, extreme = trade["fib_range"]
    annotations = {
        "bos": [rel(trade["bos_level"][0]), rel(trade["bos_idx"]), rnd(trade["bos_level"][1])],
        "ob": [rel(trade["ob_idx"]), rnd(l[trade["ob_idx"]]), rnd(h[trade["ob_idx"]])],
        "fvg": [rel(trade["fvg_idx"]), rnd(trade["fvg"][0]), rnd(trade["fvg"][1])],
        "fib": [rel(trade["anchor_idx"]), rel(trade["extreme_idx"]), rnd(anchor), rnd(extreme)],
        "touch": rel(trade["entry_idx"]),
    }
    if trade["sweep"]:
        annotations["liq"] = [rel(trade["sweep"][0]), rel(trade["anchor_idx"]), rnd(trade["sweep"][1])]
    return {
        "pair": pair,
        "p": decimals,
        "t": int(df.index[start].timestamp()),
        "st": STEP_SECONDS,
        "b": base,
        "c": candles,
        "d": rel(decision),
        "h1": htf["h1"],
        "h4": htf["h4"],
        "side": "buy" if trade["side"] == "long" else "sell",
        "risk": rnd(risk),
        "a": annotations,
        "sweep": trade["sweep"] is not None,
        "fibOk": trade["has_fib"],
    }


def main():
    smc.MIN_STOP_PCT = MIN_RISK_PCT
    scenarios = []
    for pair, decimals in PAIRS.items():
        df = load_pair(pair)
        o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
        count = 0
        for trade in collect(df):
            if df.index[trade["entry_idx"]] < START:
                continue
            decision = reversal_bar(o, h, l, c, trade)
            if decision is None or decision + 20 >= len(df):
                continue
            risk = abs(c[decision] - trade["stop"])
            if risk / c[decision] < MIN_RISK_PCT:
                continue
            scenarios.append(build(df, pair, decimals, trade, decision))
            count += 1
        print(pair, count, "situations")
    random.Random(SEED).shuffle(scenarios)
    for number, scenario in enumerate(scenarios, 1):
        scenario["id"] = number
    OUTPUT.write_text(f"window.SCENARIOS={json.dumps(scenarios, separators=(',', ':'))};\n", encoding="utf-8")
    buys = sum(s["side"] == "buy" for s in scenarios)
    print(f"{len(scenarios)} situations ({buys} achats, {len(scenarios) - buys} ventes) -> {OUTPUT}")


if __name__ == "__main__":
    main()
