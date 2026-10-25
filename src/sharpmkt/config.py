"""Paths, the league table, the season windows shared by every module."""

from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw"
DERIVED = ROOT / "data/derived"
MANIFEST = RAW / "MANIFEST.json"
SEED = 20250815
USER_AGENT = "sharpmkt-research/0.1 (https://github.com/ajaiupadhyaya)"

# The exploratory season. The confirmatory sample is 2026-27 matches that kick off after the
# pre-analysis plan is signed; nothing in this repository reads them before then.
SEASON = "2526"
SEASON_START, SEASON_END = date(2025, 7, 1), date(2026, 6, 30)

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
