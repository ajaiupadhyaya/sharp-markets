"""Generate every number, table and figure dataset the paper uses, from the 2025-26 panel.

Lives outside src/ on purpose: src/, pyproject.toml and uv.lock are frozen by the pap-v1 tag, so
the paper adds no dependency and no bound file. Figures are drawn by pgfplots from the CSVs
written here.

Run: `uv run python paper/make_inputs.py` -> paper/generated/
"""

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import polars as pl

from sharpmkt import confirm, power
from sharpmkt.config import OFFSETS
from sharpmkt.panel import PANEL

OUT = Path(__file__).resolve().parent / "generated"
VEN = {"kalshi": "Kalshi", "pm": "Polymarket", "pin": "Pinnacle", "avg": "Bookmaker average"}


def f(x: float, d: int = 4, sign: bool = True) -> str:
    s = f"{x:+.{d}f}" if sign else f"{x:.{d}f}"
    return s.replace("-", "$-$") if sign else s


def macros(m: dict) -> str:
    return "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in m.items())


def main() -> None:
    OUT.mkdir(exist_ok=True)
    panel = pl.read_parquet(PANEL)
    sc = power.scores(panel)
    m = {}

    # ---- coverage
    m["nFixtures"] = f"{panel.filter(pl.col('venue') == 'avg')['fixture_id'].n_unique():,}"
    m["nBetfair"] = f"{panel.filter(pl.col('venue') == 'bf')['fixture_id'].n_unique():,}"
    m["nLeagues"] = str(panel["div"].n_unique())
    cov = (panel.group_by("div", "venue").agg(pl.len()).pivot("venue", index="div", values="len")
           .sort("div").fill_null(0))
    rows = [f"{r['div']} & {r['bf']} & {r['kalshi']} & {r['pm']} \\\\" for r in
            cov.iter_rows(named=True)]
    (OUT / "tab_coverage.tex").write_text("\n".join(rows) + "\n")

    # ---- RQ1
    rq1 = []
    for v, label in VEN.items():
        p = power.paired(sc, v)
        s = power.summary(p, "d_ls")
        b = power.summary(p, "d_br")
        key = {"kalshi": "K", "pm": "P", "pin": "Pin", "avg": "Avg"}[v]
        m |= {f"rqOneN{key}": f"{s['n']:,}", f"rqOneMean{key}": f(s["mean"]),
              f"rqOneSe{key}": f(s["se"], 4, False), f"rqOneMde{key}": f(s["mde"], 4, False)}
        rq1.append(f"{label} & {s['n']:,} & {s['clusters']} & {f(s['mean'])} & "
                   f"{f(s['se'], 4, False)} & {f(s['mde'], 4, False)} & {f(b['mean'])} & "
                   f"{f(b['se'], 4, False)} \\\\")
    (OUT / "tab_rq1.tex").write_text("\n".join(rq1) + "\n")

    # ---- robustness and TOST on the whole exploratory season, through the confirmatory code
    t0, t1 = datetime(2025, 6, 30, tzinfo=UTC), datetime(2026, 6, 30, 23, 59, 59, tzinfo=UTC)
    w = confirm.window(panel, t0, t1)
    tests = [("H1 specification: Kalshi, log score", confirm._test(w, "kalshi")),
             ("Polymarket (H2 specification)", confirm._test(w, "pm")),
             ("Kalshi, Brier score", confirm._test(w, "kalshi", "d_br")),
             *((f"Kalshi read {o} min before kickoff", confirm._test(w, f"kalshi@{o}"))
               for o in OFFSETS if o),
             ("Kalshi, Shin de-vigging", confirm._test(confirm._shin_panel(w), "kalshi")),
             ("Kalshi, top five leagues", confirm._test(w.filter(pl.col("div").is_in(
                 list(power.TOP_TIER))), "kalshi")),
             ("Kalshi, clusters by division $\\times$ date",
              confirm._test(w, "kalshi", cluster="date")),
             ("Bookmaker average (yardstick)", confirm._test(w, "avg"))]
    rob = [f"{lab} & {r['n']:,} & {f(r['mean'])} & {f(r['se'], 4, False)} & "
           f"[{f(r['ci90'][0])}, {f(r['ci90'][1])}] & {'yes' if r['equivalent'] else 'no'} \\\\"
           for lab, r in tests]
    (OUT / "tab_robust.tex").write_text("\n".join(rob) + "\n")
    h1 = tests[0][1]
    m |= {"hOneLo": f(h1["ci90"][0]), "hOneHi": f(h1["ci90"][1]), "hOneN": f"{h1['n']:,}"}

    # ---- TOST power
    tp = []
    for v, label in (("kalshi", "Kalshi"), ("pm", "Polymarket")):
        se = power.summary(power.paired(sc, v), "d_ls")["se"]
        cells = " & ".join(f"{power.tost_power(se / np.sqrt(s), alpha=0.05):.2f}"
                           for s in power.TOST_SHARES)
        tp.append(f"{label} & {cells} \\\\")
    (OUT / "tab_power.tex").write_text("\n".join(tp) + "\n")

    # ---- RQ2 encompassing
    rq2 = []
    for v, label in (("kalshi", "Kalshi"), ("pm", "Polymarket")):
        wv = power.pair_wide(panel, v)
        res = wv["result"].replace_strict({"H": 0, "D": 1, "A": 2}).to_numpy()
        b, cov_ = power.estimators.pool([power._logp(wv, "b"), power._logp(wv, "v")], res,
                                        wv["cluster"].to_numpy())
        se = np.sqrt(np.diag(cov_))
        rq2.append(f"{label} & {wv.height:,} & {f(b[0], 2)} ({se[0]:.2f}) & {f(b[1], 2)} "
                   f"({se[1]:.2f}) & {power.Z * se[1]:.2f} \\\\")
    (OUT / "tab_rq2.tex").write_text("\n".join(rq2) + "\n")

    # ---- timing (RQ3) table and figure data, on fixtures priced at every offset
    timing_rows, fig = [], []
    for v, label in (("kalshi", "Kalshi"), ("pm", "Polymarket")):
        names = [v if o == 0 else f"{v}@{o}" for o in OFFSETS]
        common = None
        for nm in names:
            ids = set(panel.filter(pl.col("venue") == nm)["fixture_id"])
            common = ids if common is None else common & ids
        keep = pl.Series(sorted(common))
        for o, nm in zip(OFFSETS, names, strict=True):
            g = power.slope_gap(panel, nm, keep)
            d = power.summary(power.paired(sc, nm).filter(pl.col("fixture_id").is_in(
                keep.implode())), "d_ls")
            timing_rows.append(f"{label} & {o} & {d['n']:,} & {f(g['gap'], 3)} & "
                               f"{f(g['gap_se'], 3, False)} & {f(d['mean'])} & "
                               f"{f(d['se'], 4, False)} \\\\")
            fig.append({"venue": v, "offset": o, "gap": g["gap"], "lo": g["gap"] - 1.96 *
                        g["gap_se"], "hi": g["gap"] + 1.96 * g["gap_se"]})
            if o == 0:
                m[f"gapZero{'K' if v == 'kalshi' else 'P'}"] = f(g["gap"], 3)
            if o == 60:
                m[f"gapSixty{'K' if v == 'kalshi' else 'P'}"] = f(g["gap"], 3)
                m[f"gapSixtySe{'K' if v == 'kalshi' else 'P'}"] = f(g["gap_se"], 3, False)
    (OUT / "tab_timing.tex").write_text("\n".join(timing_rows) + "\n")
    fg = pl.DataFrame(fig)
    for v in ("kalshi", "pm"):
        fg.filter(pl.col("venue") == v).with_columns(
            (pl.col("hi") - pl.col("gap")).alias("err")).select("offset", "gap", "err").write_csv(
            OUT / f"fig_timing_{v}.csv")

    # ---- calibration figure: binned predicted vs observed, Kalshi and Betfair, same rows
    r = power._outcome_rows(power.pair_wide(panel, "kalshi"))
    edges = np.linspace(0, 1, 21)
    for col, name in (("p_v", "kalshi"), ("p_b", "betfair")):
        b = r.with_columns(pl.Series("bin", np.digitize(r[col].to_numpy(), edges[1:-1]))).group_by(
            "bin").agg(
            pl.col(col).mean().alias("pred"), pl.col("y").mean().alias("obs"), pl.len())
        b.filter(pl.col("len") >= 30).sort("pred").select("pred", "obs", "len").write_csv(
            OUT / f"fig_calib_{name}.csv")

    # ---- FLB returns
    flb = []
    edges_r = [0, 0.10, 0.25, 0.50, 0.75, 1.01]
    labels = ["$<0.10$", "0.10--0.25", "0.25--0.50", "0.50--0.75", "$\\geq 0.75$"]
    for lo, hi, lab in zip(edges_r[:-1], edges_r[1:], labels, strict=True):
        cells = []
        for v in ("kalshi", "pm"):
            rv = power._outcome_rows(power.pair_wide(panel, v))
            g = rv.filter((pl.col("p_v") >= lo) & (pl.col("p_v") < hi))
            ret = (g["y"] / g["p_v"] - 1).to_numpy()
            se = power.cluster_se(ret, g["cluster"].to_numpy())
            cells.append(f"{f(ret.mean(), 3)} ({f(se, 3, False)}) & {g.height:,}")
        flb.append(f"{lab} & " + " & ".join(cells) + " \\\\")
    (OUT / "tab_flb.tex").write_text("\n".join(flb) + "\n")

    # ---- RQ4
    rq4 = []
    for v, label in (("kalshi", "Kalshi"), ("pm", "Polymarket")):
        p = power.paired(sc, v).join(panel.filter(pl.col("venue") == v).select(
            "fixture_id", "venue_volume"), on="fixture_id").filter(pl.col("venue_volume") > 0)
        lv = np.log(p["venue_volume"].to_numpy())
        z = (lv - lv.mean()) / lv.std()
        top = p["div"].is_in(list(power.TOP_TIER)).cast(pl.Float64).to_numpy()
        b, cv = power.estimators.ols(np.column_stack([np.ones(len(z)), z, top]),
                                     p["d_ls"].to_numpy(), p["cluster"].to_numpy())
        se = np.sqrt(np.diag(cv))
        rq4.append(f"{label} & {p.height:,} & {f(b[1])} ({f(se[1], 4, False)}) & {f(b[2])} "
                   f"({f(se[2], 4, False)}) \\\\")
    (OUT / "tab_rq4.tex").write_text("\n".join(rq4) + "\n")

    # ---- venue quote quality
    k = panel.filter(pl.col("venue") == "kalshi")
    m |= {"kSpread": f"{k['spread'].median() * 100:.1f}",
          "kVolume": f"{k['venue_volume'].median():,.0f}",
          "kFallback": f"{k['fallback'].sum()}",
          "nKalshiEvents": "3,855", "nKalshiMatched": "3,788",
          "nPmEvents": "4,292", "nPmMatched": "4,204"}
    (OUT / "numbers.tex").write_text(macros(m))
    print(f"-> {OUT} ({len(list(OUT.iterdir()))} files)")


if __name__ == "__main__":
    main()
