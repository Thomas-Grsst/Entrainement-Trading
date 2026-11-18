"""Télécharge les bougies 5 min BTC/USDC depuis data.binance.vision (données publiques gratuites).

Usage : python3 outils/telecharger_bougies.py 2024-11 2026-10
"""
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

DEST = Path(__file__).resolve().parent / "donnees"
URL = "https://data.binance.vision/data/spot/monthly/klines/BTCUSDC/5m/BTCUSDC-5m-{month}.zip"


def months(first, last):
    year, month = map(int, first.split("-"))
    end = tuple(map(int, last.split("-")))
    while (year, month) <= end:
        yield f"{year}-{month:02d}"
        month += 1
        if month > 12:
            year, month = year + 1, 1


def main():
    first, last = sys.argv[1], sys.argv[2]
    DEST.mkdir(exist_ok=True)
    for month in months(first, last):
        with urllib.request.urlopen(URL.format(month=month)) as response:
            zipfile.ZipFile(io.BytesIO(response.read())).extractall(DEST)
        print("ok", month)


if __name__ == "__main__":
    main()
