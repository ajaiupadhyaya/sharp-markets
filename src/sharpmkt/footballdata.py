"""football-data.co.uk: results and closing 1X2 odds for the season, one CSV per division.

Kickoff times in the files are UK local time; they are converted to UTC here. Closing odds kept:
Betfair Exchange (BFEC*, the primary benchmark), Pinnacle (PSC*, 2025-26 only) and the market
average (AvgC*).

Run: `uv run python -m sharpmkt.footballdata` -> data/derived/fixtures.parquet
"""

import hashlib
import io
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import polars as pl
import requests

from sharpmkt import config, http
from sharpmkt.config import DERIVED, DIVISIONS, RAW, SEASON, USER_AGENT

URL = "https://www.football-data.co.uk/mmz4281/{season}/{div}.csv"
LONDON = ZoneInfo("Europe/London")
ODDS = {"bf": "BFEC", "pin": "PSC", "avg": "AvgC"}
FIXTURES = DERIVED / "fixtures.parquet"


def fetch(div: str, season: str = SEASON) -> tuple[bytes, dict]:
    url = URL.format(season=season, div=div)
    path = RAW / "football-data" / season / f"{div}.csv"
    if not path.exists():
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
        r.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
    body = path.read_bytes()
    return body, {str(path.relative_to(RAW)): {
        "url": url, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
        "retrieved": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(
            timespec="seconds")}}


def kickoff_utc(d: str, t: str) -> datetime:
    day = datetime.strptime(d, "%d/%m/%Y")
    hh, mm = (t or "15:00").split(":")
    return day.replace(hour=int(hh), minute=int(mm), tzinfo=LONDON).astimezone(UTC)


def parse(body: bytes, div: str) -> pl.DataFrame:
    df = pl.read_csv(io.BytesIO(body), encoding="latin-1", infer_schema_length=0,
                     truncate_ragged_lines=True)
    df = df.filter(pl.col("HomeTeam").is_not_null() & (pl.col("HomeTeam") != ""))
    cols = {"div": pl.lit(div), "home": pl.col("HomeTeam"), "away": pl.col("AwayTeam"),
            "result": pl.col("FTR")}
    for v, prefix in ODDS.items():
        for o in "HDA":
            c = f"{prefix}{o}"
            cols[f"{v}_{o}"] = (pl.col(c).cast(pl.Float64, strict=False) if c in df.columns
                                else pl.lit(None, pl.Float64))
    out = df.select(**cols, Date=pl.col("Date"), Time=pl.col("Time") if "Time" in df.columns
                    else pl.lit(None, pl.String))
    ko = [kickoff_utc(d, t) for d, t in zip(out["Date"], out["Time"], strict=True)]
    return out.with_columns(pl.Series("kickoff", ko)).drop("Date", "Time")


def main() -> None:
    config.require_season_allowed()
    parts, extra = [], {}
    for div in DIVISIONS:
        body, entry = fetch(div)
        extra.update(entry)
        parts.append(parse(body, div))
    df = pl.concat(parts).with_row_index("fixture_id")
    DERIVED.mkdir(parents=True, exist_ok=True)
    df.write_parquet(FIXTURES)
    http.record(extra)
    print(df.group_by("div").agg(pl.len(), pl.col("bf_H").is_not_null().sum().alias("with_bf"),
                                 pl.col("pin_H").is_not_null().sum().alias("with_pin"))
            .sort("div"))
    print(f"{df.height} fixtures -> {FIXTURES}")


if __name__ == "__main__":
    main()
