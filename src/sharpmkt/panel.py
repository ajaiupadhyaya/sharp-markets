"""One row per (fixture, venue): the venue's H/D/A probabilities at kickoff and the result.

Venues:
  bf     Betfair Exchange closing odds (primary benchmark), from football-data
  pin    Pinnacle closing odds (2025-26 robustness check)
  avg    market-average bookmaker closing odds (a yardstick: what "the bookmakers" price)
  kalshi mid of yes bid and ask in the last minute candle before kickoff (last trade when the
         book is one-sided or wider than MAX_SPREAD)
  pm     Polymarket's last price-history point before kickoff
Timing control: each venue is also read at each of OFFSETS minutes before kickoff, as venue
"kalshi@30", "pm@60" and so on, from the same fetched window. `stale_min` is measured from the
read time, so it is comparable across offsets.
Every venue's three numbers are divided by their sum (proportional de-vigging; the sum before
that is kept as `book`, so the raw prices are p * book; `shin` gives the robustness variant).
For Kalshi, `fallback` marks a fixture where any market used the last trade instead of the mid.
A fixture whose venue settlement disagrees with football-data's result
is dropped, and the count is printed. When a venue lists the same fixture twice, the event with
more volume is kept.

Run: `uv run python -m sharpmkt.panel` -> data/derived/panel.parquet
"""

import numpy as np
import polars as pl

from sharpmkt import config, kalshi, polymarket
from sharpmkt.config import DERIVED, OFFSETS
from sharpmkt.footballdata import FIXTURES
from sharpmkt.match import MATCHED

PANEL = DERIVED / "panel.parquet"
MAX_SPREAD = 0.10
OUTCOMES = ("H", "D", "A")


def _wide(long: pl.DataFrame, venue: str) -> pl.DataFrame:
    """long: fixture_id, outcome, p (+ extras) -> one row per fixture with p_H, p_D, p_A."""
    w = long.pivot("outcome", index="fixture_id", values="p").drop_nulls(list(OUTCOMES))
    w = w.with_columns(pl.sum_horizontal(*OUTCOMES).alias("book"))
    w = w.filter(pl.col("book") > 0).select(
        "fixture_id", *(pl.col(o) / pl.col("book") for o in OUTCOMES), "book")
    return w.rename({o: f"p_{o}" for o in OUTCOMES}).with_columns(
        pl.col("fixture_id").cast(pl.Int64), pl.lit(venue).alias("venue"))


def bookmaker(fixtures: pl.DataFrame, venue: str) -> pl.DataFrame:
    long = fixtures.select("fixture_id", *(
        (1 / pl.col(f"{venue}_{o}")).alias(o) for o in OUTCOMES)).unpivot(
        index="fixture_id", variable_name="outcome", value_name="p")
    return _wide(long.drop_nulls("p"), venue)


def shin(raw: np.ndarray, iters: int = 100) -> np.ndarray:
    """Shin (1993) de-vigging of one book of raw implied probabilities (1/odds, or a venue's
    three prices): the insider share z solves sum_i p_i(z) = 1, with
        p_i(z) = (sqrt(z^2 + 4 (1 - z) pi_i^2 / B) - z) / (2 (1 - z)),  B = sum_i pi_i.
    A book that already sums to 1 or less is just normalised."""
    b = raw.sum()
    if b <= 1:
        return raw / b

    def p(z):
        return (np.sqrt(z ** 2 + 4 * (1 - z) * raw ** 2 / b) - z) / (2 * (1 - z))

    lo, hi = 0.0, 0.5
    for _ in range(iters):  # sum p(z) falls as z rises
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if p(mid).sum() > 1 else (lo, mid)
    out = p((lo + hi) / 2)
    return out / out.sum()


def _dedupe(m: pl.DataFrame, vol: pl.DataFrame) -> pl.DataFrame:
    """Keep, per fixture, the venue event with the most volume."""
    ev = (m.join(vol, on="ticker").group_by("fixture_id", "event_id")
           .agg(pl.col("volume").sum()).sort("volume", descending=True)
           .unique("fixture_id", keep="first"))
    return m.join(ev.select("fixture_id", "event_id"), on=["fixture_id", "event_id"])


def venue(name: str, matched: pl.DataFrame, prices: pl.DataFrame,
          markets: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    m = matched.filter((pl.col("venue") == name) & ~pl.col("settle_mismatch"))
    m = _dedupe(m, markets.select("ticker", "volume"))
    j = m.join(prices, on="ticker", how="left").join(markets.select("ticker", "volume"),
                                                    on="ticker")
    if name == "kalshi":
        mid = (pl.col("bid") + pl.col("ask")) / 2
        ok = (pl.col("bid") > 0) & (pl.col("ask") < 1) & (pl.col("ask") - pl.col("bid")
                                                           <= MAX_SPREAD)
        j = j.with_columns(pl.when(ok).then(mid).otherwise(pl.col("last")).alias("p"),
                           (pl.col("ask") - pl.col("bid")).alias("spread"),
                           (~ok).fill_null(True).alias("fallback"))
    else:
        j = j.with_columns(pl.col("last").alias("p"), pl.lit(None, pl.Float64).alias("spread"),
                           pl.lit(False).alias("fallback"))
    j = j.with_columns(((pl.col("kickoff") - pl.col("ts")).dt.total_minutes()).alias("stale"))
    extras = j.group_by("fixture_id").agg(
        pl.col("volume").sum().alias("venue_volume"), pl.col("spread").mean().alias("spread"),
        pl.col("stale").max().alias("stale_min"), pl.col("fallback").any())
    return _wide(j.select("fixture_id", "outcome", "p").drop_nulls("p"), name), extras


def build() -> pl.DataFrame:
    fx = pl.read_parquet(FIXTURES).with_columns(pl.col("fixture_id").cast(pl.Int64))
    matched = pl.read_parquet(MATCHED)
    parts = [bookmaker(fx, v) for v in ("bf", "pin", "avg")]
    extras = []
    for name, mod, short in (("kalshi", kalshi, "kalshi"), ("polymarket", polymarket, "pm")):
        allp, mk = pl.read_parquet(mod.PRICES), pl.read_parquet(mod.MARKETS)
        for off in OFFSETS:  # "kalshi" is the kickoff read; "kalshi@30" is 30 minutes earlier
            label = short if off == 0 else f"{short}@{off}"
            w, e = venue(name, matched, allp.filter(pl.col("offset") == off).drop("offset"), mk)
            parts.append(w.with_columns(pl.lit(label).alias("venue")))
            extras.append(e.with_columns(pl.lit(label).alias("venue"),
                                         pl.col("stale_min") - off))
        bad = matched.filter((pl.col("venue") == name) & pl.col("settle_mismatch"))
        print(f"{name}: {bad['fixture_id'].n_unique()} fixtures dropped for a settlement mismatch")
    df = pl.concat(parts, how="diagonal")
    df = df.join(pl.concat(extras, how="diagonal"), on=["fixture_id", "venue"], how="left")
    return df.join(fx.select("fixture_id", "div", "kickoff", "home", "away", "result"),
                   on="fixture_id")


def main() -> None:
    config.require_season_allowed()
    df = build()
    df.write_parquet(PANEL)
    print(df.group_by("venue").agg(pl.len().alias("fixtures"), pl.col("book").median())
            .sort("venue"))
    print(f"-> {PANEL}")


if __name__ == "__main__":
    main()
