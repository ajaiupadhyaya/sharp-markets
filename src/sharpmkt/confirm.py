"""The single confirmatory run (pre-analysis plan, P1-P5). It runs once, after the 2026-27 window
closes.

Order of events in a real run:
  1. Binding (P1). Refuse unless `pap-v1` is an annotated tag, HEAD descends from it, every
     file under src/ and pyproject.toml / uv.lock is byte-identical to its blob at the tag
     (so this script and every module it imports are the frozen ones), and nothing under them is
     modified or untracked. T0 is the tag's tagger date.
  2. Date guard. Refuse before WINDOW_END has passed (the window is still open).
  3. Attempt marker (P3). docs/results/confirmatory.attempt is created with exclusive creation;
     while it exists this script refuses to run.
  4. Only now is 2026-27 read. The pipeline stages run in subprocesses with
     SHARPMKT_SEASON=2627 and the run token set, the only way the 2026-27 guard opens.
  5. Window guard (P2). Only fixtures kicking off after T0 and on or before WINDOW_END are kept;
     the counts before and after are written.
  6. H1, H2, robustness R1-R7 and exploratory X1-X4, as specified in the plan, written to
     docs/results/confirmatory.md with exclusive creation. Any failure after the marker writes
     its traceback there instead and re-raises.

`--dry-run [T0]` runs steps 5-6 on the exploratory season (2025-26) with no binding, marker or
date guard, writing docs/results/dryrun_2526.md, so the analysis can be tested before signing.
It refuses any window that reaches past the exploratory season.

Run: `uv run python -m sharpmkt.confirm` (once, after 2027-06-30) or
     `uv run python -m sharpmkt.confirm --dry-run 2025-12-01`
"""

import os
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import polars as pl
from scipy import stats

from sharpmkt import config, power
from sharpmkt.panel import OUTCOMES, shin

TAG = "pap-v1"
BOUND = ("src", "pyproject.toml", "uv.lock")
WINDOW_END = datetime(2027, 6, 30, 23, 59, 59, tzinfo=UTC)
RESULTS = config.ROOT / "docs/results"
MARKER = RESULTS / "confirmatory.attempt"
OUTPUT = RESULTS / "confirmatory.md"
DRY_OUTPUT = RESULTS / "dryrun_2526.md"
DELTA = power.DELTA  # 0.002 nats (D2)
ALPHA = 0.05  # each one-sided test (D1: H1 alone at 0.05)
MIN_N = 1500  # D9
STAGES = (("sharpmkt.footballdata",), ("sharpmkt.kalshi", "markets"),
          ("sharpmkt.polymarket", "markets"), ("sharpmkt.match",), ("sharpmkt.kalshi", "prices"),
          ("sharpmkt.polymarket", "prices"), ("sharpmkt.panel",))


class Refused(RuntimeError):
    """A binding or guard check failed before anything was read."""


# ---------------------------------------------------------------- binding (P1) and guards


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=check)


def check_binding(repo: Path = config.ROOT, tag: str = TAG,
                  bound: tuple[str, ...] = BOUND) -> datetime:
    """Return T0 (the tag's tagger date, UTC) or raise Refused."""
    kind = _git(repo, "cat-file", "-t", tag, check=False)
    if kind.returncode != 0:
        raise Refused(f"no tag {tag!r}")
    if kind.stdout.strip() != "tag":
        raise Refused(f"{tag!r} is a lightweight tag; the plan needs an annotated tag")
    if _git(repo, "merge-base", "--is-ancestor", tag, "HEAD", check=False).returncode != 0:
        raise Refused(f"HEAD does not descend from {tag}")
    tagged = _git(repo, "ls-tree", "-r", "--name-only", tag, "--", *bound).stdout.split()
    for path in tagged:
        want = _git(repo, "rev-parse", f"{tag}:{path}").stdout.strip()
        f = repo / path
        have = _git(repo, "hash-object", str(f)).stdout.strip() if f.exists() else "missing"
        if have != want:
            raise Refused(f"{path} differs from its blob at {tag} ({have[:12]} != {want[:12]})")
    if _git(repo, "diff", "--quiet", tag, "--", *bound, check=False).returncode != 0:
        raise Refused(f"tracked changes since {tag} under {', '.join(bound)}")
    dirty = _git(repo, "status", "--porcelain", "--untracked-files=all", "--", *bound).stdout
    if dirty.strip():
        raise Refused(f"modified or untracked files under {', '.join(bound)}:\n{dirty}")
    date = _git(repo, "for-each-ref", f"refs/tags/{tag}", "--format=%(taggerdate:iso-strict)")
    return datetime.fromisoformat(date.stdout.strip()).astimezone(UTC)


def check_window_closed(now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    if now <= WINDOW_END:
        raise Refused(f"the confirmatory window is open until {WINDOW_END:%Y-%m-%d}; "
                      "the run is after it closes")


def create_marker(path: Path = MARKER, head: str = "") -> None:
    """Exclusive creation: a second attempt finds the marker and refuses."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "x") as f:
            f.write(f"attempt started {datetime.now(UTC).isoformat(timespec='seconds')} "
                    f"at HEAD {head}\n")
    except FileExistsError as e:
        raise Refused(f"{path} exists: the confirmatory run has already been attempted") from e


def write_once(path: Path, text: str) -> None:
    with open(path, "x") as f:
        f.write(text)


# ---------------------------------------------------------------- window guard (P2)


def window(panel: pl.DataFrame, t0: datetime, t1: datetime) -> pl.DataFrame:
    """Fixtures kicking off strictly after t0 and at or before t1."""
    return panel.filter((pl.col("kickoff") > t0) & (pl.col("kickoff") <= t1))


# ---------------------------------------------------------------- tests


def tost(d: np.ndarray, cl: np.ndarray, delta: float = DELTA, alpha: float = ALPHA) -> dict:
    """Two one-sided tests of |mean| < delta with a clustered se; equivalence iff the
    (1 - 2 alpha) CI lies inside (-delta, delta), i.e. both one-sided p-values < alpha."""
    n, m = len(d), float(d.mean())
    se = power.cluster_se(d, cl)
    p_low = 1 - stats.norm.cdf((m + delta) / se)  # H0: mean <= -delta
    p_high = stats.norm.cdf((m - delta) / se)  # H0: mean >= +delta
    z90, z95 = stats.norm.ppf(1 - alpha), stats.norm.ppf(0.975)
    return {"n": n, "clusters": len(np.unique(cl)), "mean": m, "se": se,
            "ci90": (m - z90 * se, m + z90 * se), "ci95": (m - z95 * se, m + z95 * se),
            "p_tost": float(max(p_low, p_high)), "p_zero": float(2 * (1 - stats.norm.cdf(
                abs(m) / se))), "equivalent": bool(max(p_low, p_high) < alpha)}


def _row(label: str, r: dict) -> str:
    return (f"| {label} | {r['n']} | {r['clusters']} | {r['mean']:+.5f} | {r['se']:.5f} | "
            f"[{r['ci90'][0]:+.5f}, {r['ci90'][1]:+.5f}] | {r['p_tost']:.4f} | "
            f"{'yes' if r['equivalent'] else 'no'} | {r['p_zero']:.3f} |")


def _test(panel: pl.DataFrame, venue: str, col: str = "d_ls",
          cluster: str = "week") -> dict | None:
    p = power.paired(power.scores(panel), venue)
    if p.height < 2:
        return None
    if cluster == "date":
        p = p.with_columns(pl.concat_str(pl.col("div"), pl.col("kickoff").dt.strftime(
            "%Y-%m-%d")).alias("cluster"))
    return tost(p[col].to_numpy(), p["cluster"].to_numpy())


def _shin_panel(panel: pl.DataFrame) -> pl.DataFrame:
    """Every source's probabilities re-de-vigged by Shin's method from the raw prices."""
    ps = [f"p_{o}" for o in OUTCOMES]
    raw = (panel.select(ps).to_numpy() * panel["book"].to_numpy()[:, None])
    out = np.array([shin(r) if np.all(np.isfinite(r)) else r for r in raw])
    return panel.with_columns(*(pl.Series(c, out[:, i]) for i, c in enumerate(ps)))


HEADER = ("| test | matches | clusters | mean d | se (clustered) | 90% CI | TOST p | equivalent "
          f"within ±{DELTA} | p (mean = 0) |\n|---|---|---|---|---|---|---|---|---|")


def analyse(panel: pl.DataFrame, t0: datetime, t1: datetime, title: str) -> str:
    before = panel.filter(pl.col("venue") == "bf")["fixture_id"].n_unique()
    w = window(panel, t0, t1)
    after = w.filter(pl.col("venue") == "bf")["fixture_id"].n_unique()
    h1, h2 = _test(w, "kalshi"), _test(w, "pm")
    lines = [f"# {title}", "",
             f"Window: kickoff after {t0.isoformat()} and at or before {t1.isoformat()}. "
             f"Fixtures with Betfair closing odds: {before} in the season, {after} in the window.",
             "", "## H1 (confirmatory): Kalshi vs Betfair Exchange closing, log score", "",
             HEADER]
    if h1 is None:
        lines.append("| H1 | 0 | | | | | | not testable | |")
    else:
        lines.append(_row("H1 Kalshi", h1))
        if h1["n"] < MIN_N:
            lines += ["", f"**Minimum-sample rule (D9):** {h1['n']} < {MIN_N} paired fixtures, "
                      "so H1 is reported as exploratory."]
        else:
            lines += ["", f"**H1 {'is' if h1['equivalent'] else 'is not'} supported:** "
                      f"Kalshi is {'' if h1['equivalent'] else 'not shown to be '}within "
                      f"±{DELTA} nats per match of the Betfair Exchange close (TOST p = "
                      f"{h1['p_tost']:.4f}, α = {ALPHA})."]
    lines += ["", "## H2 (secondary): Polymarket vs Betfair", "", HEADER]
    if h2 is not None:
        lines.append(_row("H2 Polymarket", h2))

    lines += ["", "## Robustness (not confirmatory)", "", HEADER]
    rob = [("R1 Brier score (Kalshi)", _test(w, "kalshi", "d_br")),
           *((f"R2 Kalshi read {o} min before kickoff", _test(w, f"kalshi@{o}"))
             for o in config.OFFSETS if o),
           ("R3 Shin de-vigging (Kalshi)", _test(_shin_panel(w), "kalshi"))]
    fb = w.filter((pl.col("venue") == "kalshi") & pl.col("fallback").fill_null(False))
    rob += [("R4 Kalshi, no last-trade fallback",
             _test(w.filter(~pl.col("fixture_id").is_in(fb["fixture_id"].implode())), "kalshi")),
            ("R5 Kalshi, top five leagues", _test(w.filter(pl.col("div").is_in(
                list(power.TOP_TIER))), "kalshi")),
            ("R6 bookmaker average vs Betfair (yardstick)", _test(w, "avg")),
            ("R7 Kalshi, clusters by division x date", _test(w, "kalshi", cluster="date"))]
    for label, r in rob:
        if r is not None:
            lines.append(_row(label, r))
    lines += ["", f"R4 drops {fb.height} fixtures that used Kalshi's last-trade fallback.",
              "", "## Exploratory (labelled exploratory wherever they appear)"]
    lines += power.timing(w) + power.rq3(w) + power.rq4(w)
    lines += power.rq2(w, {"pm": "Polymarket"})
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- the run


def run_pipeline() -> Path:
    env = {**os.environ, "SHARPMKT_SEASON": config.CONFIRMATORY, config.CONFIRM_TOKEN_ENV: "1"}
    for stage in STAGES:
        subprocess.run([sys.executable, "-m", *stage], env=env, check=True, cwd=config.ROOT)
    return config.ROOT / "data/derived" / config.CONFIRMATORY / "panel.parquet"


def main(argv: list[str]) -> None:
    from sharpmkt.panel import PANEL

    if argv[:1] == ["--dry-run"]:
        if config.SEASON != config.EXPLORATORY:
            raise Refused("--dry-run is for the exploratory season only")
        start, end = config.SEASONS[config.EXPLORATORY]
        t0 = (datetime.fromisoformat(argv[1]).replace(tzinfo=UTC) if len(argv) > 1
              else datetime(start.year, start.month, start.day, tzinfo=UTC))
        t1 = datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=UTC)
        RESULTS.mkdir(parents=True, exist_ok=True)
        DRY_OUTPUT.write_text(analyse(pl.read_parquet(PANEL), t0, t1,
                                      "DRY RUN on 2025-26 (exploratory season, not a result)"))
        print(f"-> {DRY_OUTPUT}")
        return
    t0 = check_binding()
    check_window_closed()
    head = _git(config.ROOT, "rev-parse", "HEAD").stdout.strip()
    create_marker(head=head)
    try:
        text = analyse(pl.read_parquet(run_pipeline()), t0, WINDOW_END,
                       f"Confirmatory run (tag {TAG}, HEAD {head[:12]})")
        write_once(OUTPUT, text)
    except BaseException:
        write_once(OUTPUT, "# Confirmatory run FAILED after the attempt marker\n\n```\n"
                   + traceback.format_exc() + "```\n")
        raise
    print(f"-> {OUTPUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
