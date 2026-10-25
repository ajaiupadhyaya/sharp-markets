"""The confirmatory script's guards: tag binding, date guard, window, marker, the 2026-27 season
lock, and the equivalence test."""

import os
import subprocess
import sys
from datetime import UTC, datetime

import numpy as np
import polars as pl
import pytest

from sharpmkt import confirm


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/m.py").write_text("x = 1\n")
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    (tmp_path / "uv.lock").write_text("")
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.org")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "c")
    return tmp_path


def test_binding_needs_an_annotated_tag(repo):
    with pytest.raises(confirm.Refused, match="no tag"):
        confirm.check_binding(repo)
    _git(repo, "tag", "pap-v1")
    with pytest.raises(confirm.Refused, match="lightweight"):
        confirm.check_binding(repo)
    _git(repo, "tag", "-d", "pap-v1")
    _git(repo, "tag", "-a", "pap-v1", "-m", "sign")
    t0 = confirm.check_binding(repo)
    assert t0.tzinfo is not None and abs((datetime.now(UTC) - t0).total_seconds()) < 120


def test_binding_refuses_changed_or_untracked_code(repo):
    _git(repo, "tag", "-a", "pap-v1", "-m", "sign")
    (repo / "src/m.py").write_text("x = 2\n")
    with pytest.raises(confirm.Refused, match="differs"):
        confirm.check_binding(repo)
    _git(repo, "checkout", "--", "src/m.py")
    (repo / "src/shadow.py").write_text("")
    with pytest.raises(confirm.Refused, match="untracked"):
        confirm.check_binding(repo)
    (repo / "src/shadow.py").unlink()
    (repo / "src/m.py").write_text("x = 3\n")
    _git(repo, "commit", "-qam", "edit after tag")
    with pytest.raises(confirm.Refused, match="differs"):
        confirm.check_binding(repo)


def test_binding_refuses_head_off_the_tag(repo):
    _git(repo, "tag", "-a", "pap-v1", "-m", "sign")
    _git(repo, "checkout", "-q", "--orphan", "other")
    _git(repo, "commit", "-qm", "unrelated")
    with pytest.raises(confirm.Refused, match="descend"):
        confirm.check_binding(repo)


def test_date_guard():
    with pytest.raises(confirm.Refused, match="open"):
        confirm.check_window_closed(datetime(2027, 6, 30, 12, tzinfo=UTC))
    confirm.check_window_closed(datetime(2027, 7, 1, tzinfo=UTC))


def test_marker_is_single_use(tmp_path):
    m = tmp_path / "r/confirmatory.attempt"
    confirm.create_marker(m, head="abc")
    with pytest.raises(confirm.Refused, match="already been attempted"):
        confirm.create_marker(m, head="abc")
    out = tmp_path / "r/confirmatory.md"
    confirm.write_once(out, "x")
    with pytest.raises(FileExistsError):
        confirm.write_once(out, "y")


def test_window_is_strictly_after_t0():
    t0 = datetime(2026, 11, 1, 12, tzinfo=UTC)
    p = pl.DataFrame({"kickoff": [t0, datetime(2026, 11, 1, 12, 1, tzinfo=UTC),
                                  datetime(2027, 7, 1, tzinfo=UTC)]})
    assert confirm.window(p, t0, confirm.WINDOW_END).height == 1


def test_tost():
    rng = np.random.default_rng(0)
    d = rng.normal(0, 0.02, size=4000)
    r = confirm.tost(d, np.arange(4000))
    assert r["equivalent"] and r["ci90"][0] > -0.002 and r["ci90"][1] < 0.002
    r = confirm.tost(d + 0.003, np.arange(4000))
    assert not r["equivalent"] and r["p_zero"] < 0.001


@pytest.mark.parametrize("module", ["sharpmkt.footballdata", "sharpmkt.kalshi",
                                    "sharpmkt.polymarket", "sharpmkt.match", "sharpmkt.panel"])
def test_confirmatory_season_is_locked(module):
    env = {**os.environ, "SHARPMKT_SEASON": "2627"}
    env.pop("SHARPMKT_CONFIRM_RUN", None)
    r = subprocess.run([sys.executable, "-m", module], env=env, capture_output=True, text=True)
    assert r.returncode != 0 and "confirmatory season" in r.stderr


def test_dry_run_refuses_the_confirmatory_season():
    env = {**os.environ, "SHARPMKT_SEASON": "2627"}
    r = subprocess.run([sys.executable, "-m", "sharpmkt.confirm", "--dry-run"], env=env,
                       capture_output=True, text=True)
    assert r.returncode != 0 and "exploratory season only" in r.stderr
