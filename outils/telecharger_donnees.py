"""Télécharge les bougies 1 min de HistData.com (données gratuites, prix bid, fuseau EST fixe UTC-5).

Usage : python3 outils/telecharger_donnees.py
Les années passées sont des fichiers annuels, l'année en cours des fichiers mensuels.
"""
import io
import re
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://www.histdata.com"
DEST = Path(__file__).resolve().parent / "donnees" / "fx"
PAIRS = ("XAUUSD", "EURUSD", "GBPUSD")
JOBS = [(2024, None), (2025, None)] + [(2026, month) for month in range(1, 11)]


def fetch(pair, year, month=None):
    path = f"/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/{pair.lower()}/{year}"
    if month:
        path += f"/{month}"
    page_url = BASE + path
    page = urllib.request.urlopen(page_url, timeout=60).read().decode("utf-8", "ignore")
    fields = dict(re.findall(r'<input type="hidden" name="(\w+)" id="\w+" value="([^"]*)"', page))
    if "tk" not in fields:
        raise RuntimeError(f"pas de jeton de téléchargement pour {pair} {year} {month}")
    body = urllib.parse.urlencode({k: fields[k] for k in ("tk", "date", "datemonth", "platform", "timeframe", "fxpair")}).encode()
    request = urllib.request.Request(BASE + "/get.php", data=body, headers={"Referer": page_url})
    archive = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(request, timeout=120).read()))
    name = next(n for n in archive.namelist() if n.endswith(".csv"))
    target = DEST / pair / f"{year}{'' if not month else f'-{month:02d}'}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(archive.read(name))
    return target


def main():
    for pair in PAIRS:
        for year, month in JOBS:
            for attempt in range(3):
                try:
                    print("ok", fetch(pair, year, month))
                    break
                except Exception as error:
                    print("échec", pair, year, month, error)
                    time.sleep(3 * (attempt + 1))


if __name__ == "__main__":
    main()
