"""Power checks on 2025-26 for RQ1 (accuracy against the Betfair Exchange closing line) and,
further down, RQ2 (encompassing), RQ3 (favourite-longshot bias) and RQ4 (liquidity, division).

2025-26 is the exploratory season, so its estimates are shown, labelled as exploratory. The
confirmatory sample is 2026-27 matches kicking off after the plan is signed.

For every fixture priced by both a venue and Betfair, the paired score difference is
    d = log p_venue(result) - log p_bf(result)      (> 0: the venue was more accurate),
and the same for the Brier score (sign flipped so that > 0 is still "venue better"). Matches on
the same weekend in the same league share shocks, so the standard error is clustered by
(division, ISO week). MDE = (z_0.975 + z_0.80) * se.

Projection: the confirmatory window is part of a season. With a share `f` of 2025-26's matched
count, se scales by 1/sqrt(f).

Yardsticks put a log-score difference on a familiar scale: the same paired comparison for
Pinnacle and for the market-average bookmaker against Betfair.

Run: `uv run python -m sharpmkt.power` -> docs/power.md (the generated block is rewritten; text
outside it is kept)
"""

import numpy as np
import polars as pl
from scipy import stats

from sharpmkt import estimators
from sharpmkt.config import OFFSETS, ROOT
from sharpmkt.panel import OUTCOMES, PANEL

ALPHA, POWER = 0.05, 0.80
Z = stats.norm.ppf(1 - ALPHA / 2) + stats.norm.ppf(POWER)
CONFIRM_SHARES = (1.0, 0.6, 0.4)  # whole season; signing ~Dec (about 60% left); ~Feb (~40%)
OUT = ROOT / "docs/power.md"
BEGIN, FINISH = "<!-- BEGIN GENERATED: python -m sharpmkt.power -->", "<!-- END GENERATED -->"
VENUES = {"kalshi": "Kalshi", "pm": "Polymarket", "pin": "Pinnacle (yardstick)",
          "avg": "bookmaker average (yardstick)"}


def scores(panel: pl.DataFrame) -> pl.DataFrame:
    """Per (fixture, venue): log score and Brier score of the result. Fixtures without an
    H/D/A result (postponed, abandoned, not yet in the file) are dropped."""
    panel = panel.filter(pl.col("result").is_in(list(OUTCOMES)))
    y = {o: (pl.col("result") == o).cast(pl.Float64) for o in OUTCOMES}
    p_res = pl.coalesce(*(pl.when(pl.col("result") == o).then(pl.col(f"p_{o}"))
                          for o in OUTCOMES))
    return panel.with_columns(
        p_res.clip(1e-6, 1).log().alias("ls"),
        pl.sum_horizontal(*((pl.col(f"p_{o}") - y[o]) ** 2 for o in OUTCOMES)).alias("brier"))


def paired(sc: pl.DataFrame, venue: str, base: str = "bf") -> pl.DataFrame:
    a = sc.filter(pl.col("venue") == venue).select("fixture_id", "div", "kickoff",
                                                    pl.col("ls").alias("ls_v"),
                                                    pl.col("brier").alias("br_v"))
    b = sc.filter(pl.col("venue") == base).select("fixture_id", pl.col("ls").alias("ls_b"),
                                                   pl.col("brier").alias("br_b"))
    return a.join(b, on="fixture_id").with_columns(
        (pl.col("ls_v") - pl.col("ls_b")).alias("d_ls"),
        (pl.col("br_b") - pl.col("br_v")).alias("d_br"),
        pl.concat_str(pl.col("div"), pl.col("kickoff").dt.strftime("%G-%V")).alias("cluster"))


def cluster_se(d: np.ndarray, cl: np.ndarray) -> float:
    """Cluster-robust standard error of a mean."""
    n = len(d)
    r = d - d.mean()
    sums = pl.DataFrame({"c": cl, "r": r}).group_by("c").agg(pl.col("r").sum())["r"].to_numpy()
    g = len(sums)
    return float(np.sqrt((sums ** 2).sum() * g / (g - 1)) / n)


def summary(p: pl.DataFrame, col: str) -> dict:
    d, cl = p[col].to_numpy(), p["cluster"].to_numpy()
    se = cluster_se(d, cl)
    return {"n": len(d), "clusters": p["cluster"].n_unique(), "mean": float(d.mean()),
            "sd": float(d.std(ddof=1)), "se": se, "se_iid": float(d.std(ddof=1) / np.sqrt(len(d))),
            "mde": Z * se}

TOP_TIER = ("E0", "D1", "I1", "SP1", "F1")  # the five biggest leagues, for RQ4
VENUES_RQ = {"kalshi": "Kalshi", "pm": "Polymarket"}


def pair_wide(panel: pl.DataFrame, venue: str, base: str = "bf") -> pl.DataFrame:
    """One row per fixture priced by both: p_{H,D,A} for venue (_v) and base (_b)."""
    ps = [f"p_{o}" for o in OUTCOMES]
    keep = ["fixture_id", "div", "kickoff", "result", "venue_volume", "spread"]
    v = panel.filter(pl.col("venue") == venue).select(
        *keep, *(pl.col(c).alias(c + "_v") for c in ps))
    b = panel.filter(pl.col("venue") == base).select(
        "fixture_id", *(pl.col(c).alias(c + "_b") for c in ps))
    return v.join(b, on="fixture_id").filter(pl.col("result").is_in(list(OUTCOMES))).with_columns(
        pl.concat_str(pl.col("div"), pl.col("kickoff").dt.strftime("%G-%V")).alias("cluster"))


def _logp(w: pl.DataFrame, side: str) -> np.ndarray:
    return np.log(np.clip(w.select(f"p_{o}_{side}" for o in OUTCOMES).to_numpy(), 1e-6, 1))


DELTA = 0.002  # equivalence margin, nats per match: about the bookmaker-average gap to Betfair
TOST_SHARES = (1.0, 0.7, 0.6, 0.4)  # share of a season left after signing
HOLM = (0.025, 0.05)  # Holm's two steps over the two equivalence hypotheses (Kalshi, Polymarket)


def tost_power(se: float, delta: float = DELTA, alpha: float = 0.05, true: float = 0.0) -> float:
    """Power of two one-sided tests at level alpha (equivalent: the 1 - 2 alpha CI inside
    (-delta, delta)) when the true mean difference is `true`."""
    z = stats.norm.ppf(1 - alpha)
    hi = stats.norm.cdf((delta - true) / se - z)
    lo = stats.norm.cdf((-delta - true) / se + z)
    return max(0.0, float(hi - lo))


def equivalence(panel: pl.DataFrame) -> list[str]:
    sc = scores(panel)
    lines = ["", f"### RQ1 as an equivalence test (margin {DELTA} nats)", "",
             "Power of two one-sided tests (TOST) that |mean d| < margin, if the true difference "
             "is 0 and the se scales with the share of a season left after signing. Holm over "
             "{Kalshi, Polymarket}: the first step tests at 0.025, the second at 0.05.", "",
             "| venue | se, full season | " + " | ".join(
                 f"{f:.0%} of a season: power at 0.025 / 0.05" for f in TOST_SHARES) + " |",
             "|---|---|" + "---|" * len(TOST_SHARES)]
    for v, label in VENUES_RQ.items():
        se = summary(paired(sc, v), "d_ls")["se"]
        cells = [" / ".join(f"{tost_power(se / np.sqrt(f), alpha=a):.2f}" for a in HOLM)
                 for f in TOST_SHARES]
        lines.append(f"| {label} | {se:.5f} | " + " | ".join(cells) + " |")
    return lines


def rq2(panel: pl.DataFrame) -> list[str]:
    lines = ["", "### RQ2: does the venue add information beyond Betfair? (encompassing)", "",
             "Logarithmic opinion pool P(o) ~ exp(b_bf log p_bf(o) + b_v log p_v(o)), fitted by "
             "maximum likelihood, clustered by division x ISO week. b_v = 0: Betfair "
             "encompasses the venue; b_bf = 0: the venue encompasses Betfair.", "",
             "| venue | matches | b_bf (se) | b_v (se) | corr(b_bf, b_v) | MDE for b_v: full / "
             "60% / 40% |", "|---|---|---|---|---|---|"]
    for v, label in VENUES_RQ.items():
        w = pair_wide(panel, v)
        res = w["result"].replace_strict({"H": 0, "D": 1, "A": 2}).to_numpy()
        b, cov = estimators.pool([_logp(w, "b"), _logp(w, "v")], res, w["cluster"].to_numpy())
        se = np.sqrt(np.diag(cov))
        corr = cov[0, 1] / (se[0] * se[1])
        mdes = " / ".join(f"{Z * se[1] / np.sqrt(f):.3f}" for f in CONFIRM_SHARES)
        lines.append(f"| {label} | {w.height} | {b[0]:.3f} ({se[0]:.3f}) | {b[1]:.3f} "
                     f"({se[1]:.3f}) | {corr:+.2f} | {mdes} |")
    lines += ["", "The two log probabilities are nearly collinear, so the weights trade off "
              "(strongly negative correlation). The informative quantity is whether b_v is "
              "distinguishable from 0, not b_bf + b_v."]
    return lines


def _outcome_rows(w: pl.DataFrame) -> pl.DataFrame:
    """Three rows per fixture: y = 1 for the outcome that happened, logit of each source."""
    return pl.concat([w.select(
        "fixture_id", "cluster", pl.lit(o).alias("outcome"),
        (pl.col("result") == o).cast(pl.Float64).alias("y"),
        pl.col(f"p_{o}_v").alias("p_v"), pl.col(f"p_{o}_b").alias("p_b")) for o in OUTCOMES])


def _logit(p: pl.Series) -> np.ndarray:
    q = np.clip(p.to_numpy(), 1e-4, 1 - 1e-4)
    return np.log(q / (1 - q))


def rq3(panel: pl.DataFrame) -> list[str]:
    lines = ["", "### RQ3: favourite-longshot bias (calibration slope)", "",
             "Per outcome row (three per match): logit P(y = 1) = a + b * logit(p). b > 1: "
             "favourites under-priced and longshots over-priced (the FLB). Fitted jointly for "
             "venue and Betfair on the same rows, so the difference b_v - b_bf has a clustered se.",
             "", "| venue | rows | b_v (se) | b_bf (se) | b_v - b_bf (se) | MDE for b_v - b_bf: "
             "full / 60% / 40% | MDE for b_v - 1 |", "|---|---|---|---|---|---|---|"]
    for v, label in VENUES_RQ.items():
        r = _outcome_rows(pair_wide(panel, v))
        y = r["y"].to_numpy()
        lv, lb = _logit(r["p_v"]), _logit(r["p_b"])
        n = len(y)
        # stacked: venue rows then Betfair rows, separate intercept and slope for each
        x = np.zeros((2 * n, 4))
        x[:n, 0], x[:n, 1], x[n:, 2], x[n:, 3] = 1, lv, 1, lb
        b, cov = estimators.logit(x, np.concatenate([y, y]),
                                  np.concatenate([r["cluster"].to_numpy()] * 2))
        se = np.sqrt(np.diag(cov))
        diff_se = float(np.sqrt(cov[1, 1] + cov[3, 3] - 2 * cov[1, 3]))
        mdes = " / ".join(f"{Z * diff_se / np.sqrt(f):.3f}" for f in CONFIRM_SHARES)
        lines.append(f"| {label} | {n} | {b[1]:.3f} ({se[1]:.3f}) | {b[3]:.3f} ({se[3]:.3f}) | "
                     f"{b[1] - b[3]:+.3f} ({diff_se:.3f}) | {mdes} | {Z * se[1]:.3f} |")
    lines += ["", "Return to a 1-unit stake at the venue's (normalised) price, by price "
              "bucket, venue rows (exploratory; ignores fees and the spread):", "",
              "| venue | <0.10 | 0.10-0.25 | 0.25-0.50 | 0.50-0.75 | >=0.75 |",
              "|---|---|---|---|---|---|"]
    edges = [0, 0.10, 0.25, 0.50, 0.75, 1.01]
    for v, label in VENUES_RQ.items():
        r = _outcome_rows(pair_wide(panel, v))
        cells = []
        for lo, hi in zip(edges[:-1], edges[1:], strict=True):
            g = r.filter((pl.col("p_v") >= lo) & (pl.col("p_v") < hi))
            ret = (g["y"] / g["p_v"] - 1)
            se = cluster_se(ret.to_numpy(), g["cluster"].to_numpy()) if g.height > 30 else np.nan
            cells.append(f"{ret.mean():+.3f} ({se:.3f}), n {g.height}")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return lines


def slope_gap(panel: pl.DataFrame, venue: str, keep: pl.Series | None = None) -> dict:
    """Calibration slopes of the venue and Betfair on the same outcome rows, and their
    difference with a clustered se (stacked logit: separate intercept and slope per source)."""
    w = pair_wide(panel, venue)
    if keep is not None:
        w = w.filter(pl.col("fixture_id").is_in(keep.implode()))
    r = _outcome_rows(w)
    y = r["y"].to_numpy()
    n = len(y)
    x = np.zeros((2 * n, 4))
    x[:n, 0], x[:n, 1], x[n:, 2], x[n:, 3] = 1, _logit(r["p_v"]), 1, _logit(r["p_b"])
    b, cov = estimators.logit(x, np.concatenate([y, y]),
                              np.concatenate([r["cluster"].to_numpy()] * 2))
    return {"rows": n, "b_v": b[1], "b_b": b[3], "se_v": float(np.sqrt(cov[1, 1])),
            "se_b": float(np.sqrt(cov[3, 3])), "gap": b[1] - b[3],
            "gap_se": float(np.sqrt(cov[1, 1] + cov[3, 3] - 2 * cov[1, 3]))}


def timing(panel: pl.DataFrame) -> list[str]:
    """The same comparisons with the venue read 0, 30, 60 and 120 minutes before kickoff, on the
    fixtures priced at every offset (so the samples are identical)."""
    sc = scores(panel)
    lines = ["", "### Timing control: the venue read earlier", "",
             "Each venue read at kickoff and 30 / 60 / 120 minutes before it, from the same "
             "fetched candles, on the fixtures it priced at every offset. Betfair's closing "
             "snapshot is fixed. If the RQ3 gap and the RQ1 difference come from the venue "
             "being read later than Betfair, they should shrink or reverse at earlier offsets.",
             "", "| venue | read at | fixtures | median staleness (min) | RQ1 mean d (se) | "
             "RQ3 slope gap (se) | venue slope (se) |", "|---|---|---|---|---|---|---|"]
    for v, label in VENUES_RQ.items():
        names = [v if o == 0 else f"{v}@{o}" for o in OFFSETS]
        common = None
        for nm in names:
            ids = set(panel.filter(pl.col("venue") == nm)["fixture_id"])
            common = ids if common is None else common & ids
        keep = pl.Series(sorted(common))
        for o, nm in zip(OFFSETS, names, strict=True):
            p = paired(sc, nm).filter(pl.col("fixture_id").is_in(keep.implode()))
            d = summary(p, "d_ls")
            g = slope_gap(panel, nm, keep)
            stale = panel.filter((pl.col("venue") == nm)
                                 & pl.col("fixture_id").is_in(keep.implode()))["stale_min"]
            lines.append(f"| {label} | {'kickoff' if o == 0 else f'-{o} min'} | {d['n']} | "
                         f"{stale.median():.0f} | {d['mean']:+.4f} ({d['se']:.4f}) | "
                         f"{g['gap']:+.3f} ({g['gap_se']:.3f}) | {g['b_v']:.3f} "
                         f"({g['se_v']:.3f}) |")
        # does reading at kickoff rather than an hour earlier change accuracy? paired, clustered
        a = sc.filter(pl.col("venue") == v).select("fixture_id", pl.col("ls").alias("a"))
        b = sc.filter(pl.col("venue") == f"{v}@60").select("fixture_id", pl.col("ls").alias("b"))
        j = a.join(b, on="fixture_id").filter(pl.col("fixture_id").is_in(keep.implode())).join(
            paired(sc, v).select("fixture_id", "cluster"), on="fixture_id")
        dd = (j["a"] - j["b"]).to_numpy()
        lines.append(f"| {label} | kickoff vs -60 (paired change) | {len(dd)} | | {dd.mean():+.4f} "
                     f"({cluster_se(dd, j['cluster'].to_numpy()):.4f}) | | |")
    return lines


def rq4(panel: pl.DataFrame) -> list[str]:
    sc = scores(panel)
    lines = ["", "### RQ4: where the gaps are (liquidity and division)", "",
             "OLS of the per-match log-score difference d (venue minus Betfair) on the venue's "
             "standardised log volume and a top-five-league dummy, clustered. MDE is for each "
             "slope (per 1 sd of log volume; top five vs the rest).", "",
             "| venue | matches | slope on log volume (se) | top five minus rest (se) | MDE "
             "volume: full / 60% / 40% | MDE top five: full / 60% / 40% |",
             "|---|---|---|---|---|---|"]
    for v, label in VENUES_RQ.items():
        p = paired(sc, v).join(panel.filter(pl.col("venue") == v).select(
            "fixture_id", "venue_volume"), on="fixture_id").filter(pl.col("venue_volume") > 0)
        lv = np.log(p["venue_volume"].to_numpy())
        z = (lv - lv.mean()) / lv.std()
        top = p["div"].is_in(list(TOP_TIER)).cast(pl.Float64).to_numpy()
        x = np.column_stack([np.ones(len(z)), z, top])
        b, cov = estimators.ols(x, p["d_ls"].to_numpy(), p["cluster"].to_numpy())
        se = np.sqrt(np.diag(cov))
        m1 = " / ".join(f"{Z * se[1] / np.sqrt(f):.4f}" for f in CONFIRM_SHARES)
        m2 = " / ".join(f"{Z * se[2] / np.sqrt(f):.4f}" for f in CONFIRM_SHARES)
        lines.append(f"| {label} | {p.height} | {b[1]:+.4f} ({se[1]:.4f}) | {b[2]:+.4f} "
                     f"({se[2]:.4f}) | {m1} | {m2} |")
    lines += ["", "Mean d by division (exploratory):", "", "| div | Kalshi n | Kalshi mean d "
              "(se) | Polymarket n | Polymarket mean d (se) |", "|---|---|---|---|---|"]
    by = {}
    for v in VENUES_RQ:
        p = paired(sc, v)
        for (div,), g in p.group_by("div"):
            by.setdefault(div, {})[v] = (g.height, g["d_ls"].mean(),
                                         cluster_se(g["d_ls"].to_numpy(), g["cluster"].to_numpy())
                                         if g.height > 30 else np.nan)
    for div in sorted(by):
        cells = []
        for v in VENUES_RQ:
            n, m, s = by[div].get(v, (0, np.nan, np.nan))
            cells += [str(n), f"{m:+.4f} ({s:.4f})" if n else ""]
        lines.append(f"| {div} | " + " | ".join(cells) + " |")
    return lines


def report(panel: pl.DataFrame) -> str:
    sc = scores(panel)
    n_fx = panel.filter(pl.col("venue") == "bf")["fixture_id"].n_unique()
    lines = [
        f"Betfair closing priced {n_fx} fixtures across "
        f"{panel['div'].n_unique()} divisions (2025-26). Paired with each venue on the "
        f"fixtures both priced.",
        "",
        "### RQ1: accuracy against Betfair Exchange closing (exploratory, 2025-26)",
        "",
        "Log score per match, venue minus Betfair (> 0: venue more accurate), clustered by "
        "division x ISO week.",
        "",
        "| venue | matches | clusters | mean d (nats) | sd per match | se (clustered) | "
        "se (iid) | MDE, full season | MDE, 60% | MDE, 40% |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    rows = {}
    for v, label in VENUES.items():
        p = paired(sc, v)
        if p.height < 30:
            lines.append(f"| {label} | {p.height} | | | | | | | | |")
            continue
        s = rows[v] = summary(p, "d_ls")
        mdes = " | ".join(f"{s['mde'] / np.sqrt(f):.4f}" for f in CONFIRM_SHARES)
        lines.append(f"| {label} | {s['n']} | {s['clusters']} | {s['mean']:+.4f} | "
                     f"{s['sd']:.4f} | {s['se']:.4f} | {s['se_iid']:.4f} | {mdes} |")
    lines += ["", "Brier score, Betfair minus venue (> 0: venue more accurate):", "",
              "| venue | matches | mean d | se (clustered) | MDE, full season |",
              "|---|---|---|---|---|"]
    for v, label in VENUES.items():
        p = paired(sc, v)
        if p.height < 30:
            continue
        s = summary(p, "d_br")
        lines.append(f"| {label} | {s['n']} | {s['mean']:+.4f} | {s['se']:.4f} | "
                     f"{s['mde']:.4f} |")
    lines += ["", "### Coverage by division (fixtures priced)", "",
              "| div | bf | kalshi | polymarket | pinnacle |", "|---|---|---|---|---|"]
    cov = panel.group_by("div", "venue").agg(pl.len()).pivot("venue", index="div",
                                                              values="len").sort("div")
    for r in cov.iter_rows(named=True):
        lines.append(f"| {r['div']} | {r.get('bf') or 0} | {r.get('kalshi') or 0} | "
                     f"{r.get('pm') or 0} | {r.get('pin') or 0} |")
    k = panel.filter(pl.col("venue") == "kalshi")
    pm = panel.filter(pl.col("venue") == "pm")
    lines += ["", "### Venue quotes at kickoff", "",
              f"Kalshi: median summed book {k['book'].median():.3f}, median spread "
              f"{k['spread'].median():.3f}, median staleness of the last candle "
              f"{k['stale_min'].median():.0f} min; median volume per fixture "
              f"{k['venue_volume'].median():,.0f} contracts.",
              f"Polymarket: median summed book {pm['book'].median():.3f}, median staleness "
              f"{pm['stale_min'].median():.0f} min; median reported volume per fixture "
              f"${pm['venue_volume'].median():,.0f} (reported volume includes wash trading).",
              ]
    lines += equivalence(panel) + rq2(panel) + rq3(panel) + timing(panel) + rq4(panel)
    return "\n".join(lines)


def write(text: str) -> None:
    body = f"{BEGIN}\n{text}\n{FINISH}"
    if OUT.exists() and BEGIN in (old := OUT.read_text()) and FINISH in old:
        head, rest = old.split(BEGIN, 1)
        OUT.write_text(head + body + rest.split(FINISH, 1)[1])
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("# Power check (2025-26, exploratory)\n\n" + body + "\n")


def main() -> None:
    text = report(pl.read_parquet(PANEL))
    write(text)
    print(text)


if __name__ == "__main__":
    main()
