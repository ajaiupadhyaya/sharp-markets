"""Kalshi: settled match-winner markets (home / away / tie) and their prices before kickoff.

Two stages. `markets()` lists every settled market of each league's GAME series in the season
(three per match). Markets older than a few months only answer under /historical/..., which can
page a whole series at once.
`prices()` then reads, for each matched market, minute candlesticks over the PRE_KICKOFF_MINUTES
before kickoff (kickoff from football-data, since older Kalshi markets carry no start time) and
keeps the last one at or before kickoff, and at each timing-control offset before it (OFFSETS):
bid, ask, last price, volume and open interest.

Run: `uv run python -m sharpmkt.kalshi markets` / `... prices` (after `sharpmkt.match`)
"""

import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime

import polars as pl

from sharpmkt import http
from sharpmkt.config import (
    DERIVED,
    LEAGUES,
    OFFSETS,
    PRE_KICKOFF_MINUTES,
    SEASON_END,
    SEASON_START,
)

API = "https://api.elections.kalshi.com/trade-api/v2"
MARKETS = DERIVED / "kalshi_markets.parquet"
PRICES = DERIVED / "kalshi_prices.parquet"
MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
WORKERS = 6


def ticker_date(event_ticker: str) -> date | None:
    """KXEPLGAME-25AUG15LFCBOU -> 2025-08-15."""
    try:
        code = event_ticker.split("-")[1]
        return date(2000 + int(code[:2]), MONTHS[code[2:5]], int(code[5:7]))
    except (IndexError, KeyError, ValueError):
        return None


def series_markets(series: str, historical: bool) -> list[dict]:
    """Every settled market of a series: /historical/markets pages a whole series 1,000 at a
    time; the live endpoint holds only the last few months."""
    base = (f"{API}/historical/markets?series_ticker={series}&limit=1000" if historical
            else f"{API}/markets?series_ticker={series}&status=settled&limit=1000")
    out, cursor = [], ""
    while True:
        d = http.get_json(base + (f"&cursor={cursor}" if cursor else ""))
        out += d["markets"]
        cursor = d.get("cursor")
        if not cursor or not d["markets"]:
            return out


def markets() -> pl.DataFrame:
    rows = []
    for div, _, series, _ in LEAGUES:
        n = set()
        for hist in (True, False):
            for m in series_markets(series, hist):
                d = ticker_date(m["event_ticker"])
                if not d or not SEASON_START <= d <= SEASON_END:
                    continue
                n.add(m["event_ticker"])
                rows.append({
                    "div": div, "series": series, "event_ticker": m["event_ticker"],
                    "date": d, "ticker": m["ticker"], "side": m["ticker"].rsplit("-", 1)[1],
                    "name": m.get("yes_sub_title") or "", "result": m.get("result"),
                    "volume": float(m.get("volume_fp") or m.get("volume") or 0),
                    "historical": hist})
        print(div, series, len(n), "events", flush=True)
    return pl.DataFrame(rows).unique("ticker", keep="first")


def kickoff_candle(ticker: str, series: str, historical: bool, kickoff: datetime) -> list[dict]:
    """The last minute candle at or before kickoff minus each of OFFSETS (one row per offset)."""
    end = int(kickoff.timestamp())
    start = end - 60 * PRE_KICKOFF_MINUTES
    q = f"candlesticks?start_ts={start}&end_ts={end}&period_interval=1"
    url = (f"{API}/historical/markets/{ticker}/{q}" if historical
           else f"{API}/series/{series}/markets/{ticker}/{q}")
    d = http.get_json(url) or {}
    rows = []
    for off in OFFSETS:
        cut = end - 60 * off
        cs = [c for c in d.get("candlesticks", []) if c["end_period_ts"] <= cut]
        if not cs:
            rows.append({"ticker": ticker, "offset": off, "n_candles": 0})
            continue
        last = cs[-1]

        def f(block, key, last=last):
            b = last.get(block) or {}
            v = b.get(key, b.get(key + "_dollars"))
            return float(v) if v not in (None, "") else None

        rows.append({
            "ticker": ticker, "offset": off, "n_candles": len(cs),
            "ts": datetime.fromtimestamp(last["end_period_ts"], UTC),
            "bid": f("yes_bid", "close"), "ask": f("yes_ask", "close"),
            "last": f("price", "close"),
            "open_interest": float(last.get("open_interest") or last.get("open_interest_fp")
                                   or 0),
            "vol_window": sum(float(c.get("volume") or c.get("volume_fp") or 0) for c in cs)})
    return rows


def prices(matched: pl.DataFrame) -> pl.DataFrame:
    """matched: one row per Kalshi market with series, historical and kickoff (UTC)."""
    rows = matched.select("ticker", "series", "historical", "kickoff").to_dicts()
    with ThreadPoolExecutor(WORKERS) as pool:
        out = list(pool.map(lambda r: kickoff_candle(r["ticker"], r["series"], r["historical"],
                                                     r["kickoff"]), rows))
    return pl.DataFrame([x for xs in out for x in xs], infer_schema_length=None)


def main() -> None:
    stage = sys.argv[1] if len(sys.argv) > 1 else "markets"
    DERIVED.mkdir(parents=True, exist_ok=True)
    if stage == "markets":
        df = markets()
        df.write_parquet(MARKETS)
        print(f"{df['event_ticker'].n_unique()} events, {df.height} markets -> {MARKETS}")
    else:
        from sharpmkt.match import MATCHED
        m = pl.read_parquet(MATCHED).filter(pl.col("venue") == "kalshi")
        df = prices(m.join(pl.read_parquet(MARKETS).select("ticker", "series", "historical"),
                           on="ticker"))
        df.write_parquet(PRICES)
        print(f"{df.height} market-offsets, {df.filter(pl.col('n_candles') > 0).height} priced "
              f"-> {PRICES}")
    http.record()


if __name__ == "__main__":
    main()
