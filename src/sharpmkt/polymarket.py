"""Polymarket: closed match events (three Yes/No markets: home win, draw, away win) and the price
of each market's Yes token before kickoff.

`markets()` pages through each league's series on the Gamma API. `prices()` reads the CLOB
price history over the PRE_KICKOFF_MINUTES before the event's own kickoff time
(`gameStartTime`). The history needs explicit startTs/endTs: `interval=max` returns nothing for
resolved markets. Polymarket's price is the order-book midpoint (or the last trade when the
spread is wide), sampled per minute. The same history is also read at each timing-control
offset before kickoff (OFFSETS).

Run: `uv run python -m sharpmkt.polymarket markets` / `... prices` (after `sharpmkt.match`)
"""

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import polars as pl

from sharpmkt import config, http
from sharpmkt.config import (
    DERIVED,
    LEAGUES,
    OFFSETS,
    PRE_KICKOFF_MINUTES,
    SEASON_END,
    SEASON_START,
)

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
MARKETS = DERIVED / "polymarket_markets.parquet"
PRICES = DERIVED / "polymarket_prices.parquet"
PAGE = 100
WORKERS = 6
WIN = re.compile(r"^Will (.+?) win on \d{4}-\d{2}-\d{2}\?$")
DRAW = re.compile(r"end in a draw\?$")


def _time(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.replace("Z", "+00:00").replace(" ", "T")
    if re.search(r"[+-]\d{2}$", s):
        s += ":00"
    t = datetime.fromisoformat(s)
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def events(series_id: str) -> list[dict]:
    out, offset = [], 0
    while True:
        page = http.get_json(f"{GAMMA}/events?series_id={series_id}&closed=true&limit={PAGE}"
                             f"&offset={offset}&order=startDate&ascending=true")
        out += page
        if len(page) < PAGE:
            return out
        offset += PAGE


def markets() -> pl.DataFrame:
    rows = []
    for div, _, _, series_id in LEAGUES:
        n = 0
        for e in events(series_id):
            ms = e.get("markets") or []
            qs = [m.get("question") or "" for m in ms]
            if (len(ms) != 3 or sum(bool(WIN.match(q)) for q in qs) != 2
                    or sum(bool(DRAW.search(q)) for q in qs) != 1):
                continue  # halftime results, spreads, totals, season winners, ...
            ko = _time(ms[0].get("gameStartTime")) or _time(e.get("endDate"))
            if not ko or not (SEASON_START <= ko.date() <= SEASON_END):
                continue
            n += 1
            for m in ms:
                q = m.get("question") or ""
                w = WIN.match(q)
                side, name = ("D", "") if DRAW.search(q) else ("?", w.group(1))
                prices_final = json.loads(m.get("outcomePrices") or "[]")
                rows.append({
                    "div": div, "event_id": str(e["id"]), "title": e["title"], "kickoff_pm": ko,
                    "ticker": json.loads(m["clobTokenIds"])[0], "market_id": str(m["id"]),
                    "side": side, "name": name, "question": q,
                    "result": ("yes" if prices_final and float(prices_final[0]) > 0.5
                               else "no"),
                    "volume": float(m.get("volumeNum") or m.get("volume") or 0)})
        print(div, series_id, n, "match events", flush=True)
    return pl.DataFrame(rows)


def kickoff_price(token: str, kickoff: datetime) -> list[dict]:
    """The last price point at or before kickoff minus each of OFFSETS (one row per offset)."""
    end = int(kickoff.timestamp())
    d = http.get_json(f"{CLOB}/prices-history?market={token}&startTs="
                      f"{end - 60 * PRE_KICKOFF_MINUTES}&endTs={end}&fidelity=1") or {}
    rows = []
    for off in OFFSETS:
        pts = [p for p in d.get("history", []) if p["t"] <= end - 60 * off]
        rows.append({"ticker": token, "offset": off, "n_points": len(pts)} if not pts else {
            "ticker": token, "offset": off, "n_points": len(pts),
            "ts": datetime.fromtimestamp(pts[-1]["t"], UTC), "last": float(pts[-1]["p"])})
    return rows


def prices(matched: pl.DataFrame) -> pl.DataFrame:
    rows = matched.select("ticker", "kickoff").to_dicts()
    with ThreadPoolExecutor(WORKERS) as pool:
        out = list(pool.map(lambda r: kickoff_price(r["ticker"], r["kickoff"]), rows))
    return pl.DataFrame([x for xs in out for x in xs], infer_schema_length=None)


def main() -> None:
    config.require_season_allowed()
    stage = sys.argv[1] if len(sys.argv) > 1 else "markets"
    DERIVED.mkdir(parents=True, exist_ok=True)
    if stage == "markets":
        df = markets()
        df.write_parquet(MARKETS)
        print(f"{df['event_id'].n_unique()} events, {df.height} markets -> {MARKETS}")
    else:
        from sharpmkt.match import MATCHED
        df = prices(pl.read_parquet(MATCHED).filter(pl.col("venue") == "polymarket"))
        df.write_parquet(PRICES)
        print(f"{df.height} market-offsets, {df.filter(pl.col('n_points') > 0).height} priced "
              f"-> {PRICES}")
    http.record()


if __name__ == "__main__":
    main()
