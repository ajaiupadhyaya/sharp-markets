"""Paths, the league table, the season windows shared by every module.

The season is chosen by the environment variable SHARPMKT_SEASON: "2526" (the exploratory
season, the default) or "2627" (the confirmatory season). 2026-27 derived files live in their own
directory. Reading 2026-27 outside the confirmatory run is refused (`require_season_allowed`):
its outcomes are the confirmatory sample.
"""

import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw"
MANIFEST = RAW / "MANIFEST.json"

EXPLORATORY, CONFIRMATORY = "2526", "2627"
SEASONS = {EXPLORATORY: (date(2025, 7, 1), date(2026, 6, 30)),
           CONFIRMATORY: (date(2026, 7, 1), date(2027, 6, 30))}
SEASON = os.environ.get("SHARPMKT_SEASON", EXPLORATORY)
if SEASON not in SEASONS:
    raise ValueError(f"SHARPMKT_SEASON={SEASON!r}: expected one of {sorted(SEASONS)}")
SEASON_START, SEASON_END = SEASONS[SEASON]
DERIVED = ROOT / "data/derived" if SEASON == EXPLORATORY else ROOT / "data/derived" / SEASON
# Set only by `sharpmkt.confirm`, after its binding checks pass and its attempt marker exists.
CONFIRM_TOKEN_ENV = "SHARPMKT_CONFIRM_RUN"


def require_season_allowed() -> None:
    """Every network or outcome-reading entry point calls this first."""
    if SEASON == CONFIRMATORY and not os.environ.get(CONFIRM_TOKEN_ENV):
        raise PermissionError(
            "2026-27 is the confirmatory season: it is read only by `python -m sharpmkt.confirm`, "
            "after the pre-analysis plan is tagged (pre-analysis plan, P1-P3)")
SEED = 20250815
USER_AGENT = "sharpmkt-research/0.1 (https://github.com/ajaiupadhyaya)"


# (football-data division, name, Kalshi series ticker, Polymarket series id). Every league
# football-data covers that both venues list match-winner markets for. Kalshi lists no English
# League Two; Polymarket lists no Polymarket-only leagues here by construction.
LEAGUES = (
    ("E0", "Premier League", "KXEPLGAME", "10188"),
    ("E1", "EFL Championship", "KXEFLCHAMPIONSHIPGAME", "10355"),
    ("E2", "EFL League One", "KXEFLL1GAME", "11435"),
    ("EC", "National League", "KXENGNLGAME", "11445"),
    ("SC0", "Scottish Premiership", "KXSCOTTISHPREMGAME", "10674"),
    ("D1", "Bundesliga", "KXBUNDESLIGAGAME", "10194"),
    ("D2", "2. Bundesliga", "KXBUNDESLIGA2GAME", "10670"),
    ("I1", "Serie A", "KXSERIEAGAME", "10203"),
    ("I2", "Serie B", "KXSERIEBGAME", "10676"),
    ("SP1", "LaLiga", "KXLALIGAGAME", "10193"),
    ("SP2", "LaLiga2", "KXLALIGA2GAME", "10672"),
    ("F1", "Ligue 1", "KXLIGUE1GAME", "10195"),
    ("F2", "Ligue 2", "KXLIGUE2GAME", "10675"),
    ("N1", "Eredivisie", "KXEREDIVISIEGAME", "10286"),
    ("B1", "Belgian Pro League", "KXBELGIANPLGAME", "12351"),
    ("P1", "Primeira Liga", "KXLIGAPORTUGALGAME", "10330"),
    ("T1", "Super Lig", "KXSUPERLIGGAME", "10292"),
    ("G1", "Greek Super League", "KXSLGREECEGAME", "12356"),
)
DIVISIONS = tuple(x[0] for x in LEAGUES)

# Venue prices are read at the last observation at or before kickoff, inside this window.
PRE_KICKOFF_MINUTES = 180
# Timing control: the same fetched window read at kickoff and at these minutes before it.
OFFSETS = (0, 30, 60, 120)
