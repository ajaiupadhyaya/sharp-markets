"""Unit checks on the pieces the power check rests on: dates, names, de-vigging, scoring and
the clustered standard error."""

from datetime import UTC, date, datetime

import numpy as np
import polars as pl
import pytest

from sharpmkt import footballdata, kalshi, match, panel, polymarket, power


def test_kalshi_ticker_date():
    assert kalshi.ticker_date("KXEPLGAME-25AUG15LFCBOU") == date(2025, 8, 15)
    assert kalshi.ticker_date("KXSERIEBGAME-26MAY22FCSBAR") == date(2026, 5, 22)
    assert kalshi.ticker_date("garbage") is None


def test_kickoff_is_converted_from_uk_time():
    assert footballdata.kickoff_utc("15/08/2025", "20:00") == datetime(2025, 8, 15, 19, tzinfo=UTC)
    assert footballdata.kickoff_utc("10/01/2026", "15:00") == datetime(2026, 1, 10, 15, tzinfo=UTC)


@pytest.mark.parametrize("venue_name, fd_name", [
    ("Manchester City", "Man City"), ("Nottingham", "Nott'm Forest"),
    ("Atletico Madrid", "Ath Madrid"), ("Borussia Mönchengladbach", "M'gladbach"),
    ("Paris Saint-Germain FC", "Paris SG"), ("Wolverhampton Wanderers FC", "Wolves"),
    ("Sporting CP", "Sp Lisbon"), ("Eintracht Frankfurt", "Ein Frankfurt"),
])
def test_team_names_match(venue_name, fd_name):
    assert match.sim(venue_name, fd_name) >= 0.5


def test_unrelated_teams_score_low():
    assert match.sim("Liverpool", "Bournemouth") < 0.5
    assert match.sim("Real Madrid", "Ath Madrid") < match.sim("Atletico Madrid", "Ath Madrid")


def test_assign_finds_orientation_and_rejects_ambiguity():
    fx = pl.DataFrame({"fixture_id": [0, 1], "div": ["E0", "E0"],
                       "home": ["Liverpool", "Arsenal"], "away": ["Bournemouth", "Chelsea"],
                       "kickoff": [datetime(2025, 8, 15, 19, tzinfo=UTC)] * 2})
    ev = pl.DataFrame({"div": ["E0"] * 3, "event_id": ["e"] * 3, "date": [date(2025, 8, 15)] * 3,
                       "ticker": ["t-bou", "t-lfc", "t-tie"], "side": ["?", "?", "D"],
                       "name": ["Bournemouth", "Liverpool", "Tie"]})
    m = {r["ticker"]: (r["outcome"], r["fixture_id"])
         for r in match.assign(ev, fx, "date").iter_rows(named=True)}
    assert m == {"t-lfc": ("H", 0), "t-bou": ("A", 0), "t-tie": ("D", 0)}


def test_polymarket_question_patterns():
    assert polymarket.WIN.match("Will Liverpool win on 2025-08-15?").group(1) == "Liverpool"
    assert polymarket.DRAW.search("Will Liverpool vs. Bournemouth end in a draw?")
    assert not polymarket.WIN.match("Liverpool leading at halftime?")


def test_bookmaker_devig_sums_to_one():
    fx = pl.DataFrame({"fixture_id": [0], "bf_H": [2.0], "bf_D": [4.0], "bf_A": [4.0]})
    w = panel.bookmaker(fx, "bf")
    assert w["book"][0] == pytest.approx(1.0)
    assert (w["p_H"][0], w["p_D"][0], w["p_A"][0]) == pytest.approx((0.5, 0.25, 0.25))


def test_scores_and_paired_difference():
    pan = pl.DataFrame({
        "fixture_id": [0, 0], "venue": ["bf", "kalshi"], "div": ["E0"] * 2,
        "kickoff": [datetime(2025, 8, 15, tzinfo=UTC)] * 2, "result": ["H"] * 2,
        "p_H": [0.5, 0.6], "p_D": [0.25, 0.2], "p_A": [0.25, 0.2]})
    p = power.paired(power.scores(pan), "kalshi")
    assert p["d_ls"][0] == pytest.approx(np.log(0.6) - np.log(0.5))
    assert p["d_br"][0] == pytest.approx((0.25 + 0.0625 * 2) - (0.16 + 0.04 * 2))


def test_cluster_se_matches_iid_with_singleton_clusters():
    rng = np.random.default_rng(0)
    d = rng.normal(size=400)
    se = power.cluster_se(d, np.arange(400))
    assert se == pytest.approx(d.std(ddof=1) / np.sqrt(400), rel=0.01)
    # one shared shock per cluster inflates the clustered se above the iid one
    cl = np.repeat(np.arange(40), 10)
    d2 = d + np.repeat(rng.normal(size=40), 10)
    assert power.cluster_se(d2, cl) > d2.std(ddof=1) / np.sqrt(400) * 1.5


def test_offsets_pick_the_last_candle_before_each_cut(monkeypatch):
    ko = datetime(2025, 8, 15, 19, tzinfo=UTC)
    end = int(ko.timestamp())
    candles = [{"end_period_ts": end - 60 * m, "yes_bid": {"close": f"{0.5 - m / 1000:.3f}"},
                "yes_ask": {"close": "0.6"}, "price": {"close": "0.55"}, "volume": "1"}
               for m in (150, 100, 45, 20, 0)]
    monkeypatch.setattr(kalshi.http, "get_json", lambda url: {"candlesticks": candles})
    rows = {r["offset"]: r for r in kalshi.kickoff_candle("T", "S", True, ko)}
    assert rows[0]["ts"] == ko
    assert rows[30]["ts"] == datetime.fromtimestamp(end - 60 * 45, UTC)
    assert rows[60]["ts"] == datetime.fromtimestamp(end - 60 * 100, UTC)
    assert rows[120]["ts"] == datetime.fromtimestamp(end - 60 * 150, UTC)
    assert rows[120]["bid"] == pytest.approx(0.35)
