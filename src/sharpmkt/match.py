"""Match each venue's match events to football-data fixtures, and each market to H, D or A.

For every venue event, the candidates are the fixtures of the same division kicking off within
a day of the venue's date. The event's two team markets are assigned to (home, away) or
(away, home), whichever gives the higher name similarity, and the event goes to the
best-scoring fixture if that score clears MIN_SCORE and beats the runner-up by MIN_MARGIN.
Settlement then checks the match: the venue's winning market must agree with football-data's
full-time result, and the mismatch rate is reported, not hidden.

Run: `uv run python -m sharpmkt.match` -> data/derived/matched.parquet
"""

import re
import unicodedata
from datetime import timedelta
from difflib import SequenceMatcher

import polars as pl

from sharpmkt import config, kalshi, polymarket
from sharpmkt.config import DERIVED
from sharpmkt.footballdata import FIXTURES

MATCHED = DERIVED / "matched.parquet"
MIN_SCORE, MIN_MARGIN = 1.0, 0.15  # summed over the two teams; each similarity is in [0, 1]

# football-data's abbreviations, expanded before comparing.
ALIASES = {"man": "manchester", "utd": "united", "ath": "atletico", "nott'm": "nottingham",
           "nottm": "nottingham", "sp": "sporting", "m'gladbach": "monchengladbach",
           "mgladbach": "monchengladbach", "ein": "eintracht",
           "sheffield weds": "sheffield wednesday",
           "psg": "paris saint germain", "paris sg": "paris saint germain",
           "wolves": "wolverhampton", "spurs": "tottenham", "qpr": "queens park rangers",
           "west brom": "west bromwich", "inter": "internazionale", "dortmund": "dortmund",
           "leverkusen": "leverkusen", "st": "saint", "betis": "betis",
           "sociedad": "sociedad", "fortuna": "fortuna"}
DROP = {"fc", "afc", "cf", "sc", "ac", "as", "ss", "us", "cd", "ud", "sd", "rc", "rcd", "sv",
        "vfl", "vfb", "fsv", "tsg", "bsc", "club", "de", "calcio", "football", "futbol",
        "the", "1", "1.", "fk", "sk", "if", "bk", "cfc", "town", "city", "hotspur"}


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ").replace(".", " ").replace("-", " ")
    for k, v in sorted(ALIASES.items(), key=lambda kv: -len(kv[0])):
        s = re.sub(rf"(?<![a-z']){re.escape(k)}(?![a-z'])", v, s)
    return " ".join(t for t in s.split() if t not in DROP)


def sim(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    ta, tb = set(a.split()), set(b.split())
    token = len(ta & tb) / min(len(ta), len(tb))
    return max(token, SequenceMatcher(None, a, b).ratio(),
               1.0 if (a in b or b in a) else 0.0)


def assign(events: pl.DataFrame, fixtures: pl.DataFrame, date_col: str) -> pl.DataFrame:
    """events: one row per (event_id, team market) with div, event_id, date-ish, ticker, name."""
    out = []
    fx = fixtures.with_columns(pl.col("kickoff").dt.date().alias("kdate"))
    for (div, eid), g in events.group_by("div", "event_id", maintain_order=True):
        teams = g.filter(pl.col("side") != "D")
        if teams.height != 2:
            continue
        d = g[date_col][0]
        d = d.date() if hasattr(d, "date") else d
        cand = fx.filter((pl.col("div") == div)
                         & pl.col("kdate").is_between(d - timedelta(1), d + timedelta(1)))
        (t1, n1), (t2, n2) = teams.select("ticker", "name").rows()
        scores = []
        for f in cand.iter_rows(named=True):
            straight = sim(n1, f["home"]) + sim(n2, f["away"])
            swapped = sim(n2, f["home"]) + sim(n1, f["away"])
            scores.append((max(straight, swapped), straight >= swapped, f))
        if not scores:
            continue
        scores.sort(key=lambda x: -x[0])
        best, runner = scores[0], (scores[1][0] if len(scores) > 1 else 0.0)
        if best[0] < MIN_SCORE or best[0] - runner < MIN_MARGIN:
            continue
        f = best[2]
        home_t, away_t = (t1, t2) if best[1] else (t2, t1)
        draw = g.filter(pl.col("side") == "D")["ticker"]
        for tick, outcome in ((home_t, "H"), (away_t, "A"), *((t, "D") for t in draw)):
            out.append({"div": div, "event_id": str(eid), "ticker": tick, "outcome": outcome,
                        "fixture_id": f["fixture_id"], "kickoff": f["kickoff"],
                        "score": best[0], "margin": best[0] - runner})
    return pl.DataFrame(out)


def build() -> pl.DataFrame:
    fixtures = pl.read_parquet(FIXTURES)
    k = pl.read_parquet(kalshi.MARKETS).with_columns(
        pl.when(pl.col("side") == "TIE").then(pl.lit("D")).otherwise(pl.lit("?")).alias("side"),
        pl.col("event_ticker").alias("event_id"))
    p = pl.read_parquet(polymarket.MARKETS)
    parts = []
    for venue, ev, dcol in (("kalshi", k, "date"), ("polymarket", p, "kickoff_pm")):
        m = assign(ev, fixtures, dcol).with_columns(pl.lit(venue).alias("venue"))
        res = m.join(ev.select("ticker", "result"), on="ticker").join(
            fixtures.select("fixture_id", pl.col("result").alias("ftr")), on="fixture_id")
        won = res.filter(pl.col("result") == "yes")
        bad = won.filter(pl.col("outcome") != pl.col("ftr"))["fixture_id"].unique()
        print(f"{venue}: {ev['event_id'].n_unique()} events, {m['fixture_id'].n_unique()} "
              f"matched; settlement disagrees with football-data on {bad.len()}")
        parts.append(m.with_columns(pl.col("fixture_id").is_in(bad.implode()).alias(
            "settle_mismatch")))
    return pl.concat(parts)


def main() -> None:
    config.require_season_allowed()
    df = build()
    df.write_parquet(MATCHED)
    print(f"{df.height} market rows -> {MATCHED}")


if __name__ == "__main__":
    main()
