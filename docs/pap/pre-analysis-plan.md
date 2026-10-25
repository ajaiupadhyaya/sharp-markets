# Pre-analysis plan: *Are Prediction Markets Sharp?*

**Status: DRAFT, not signed (2026-10-25).** Nothing here binds until Ajai signs §0.1 and the
annotated git tag `pap-v1` marks the frozen state. Each **[PROPOSED — Ajai to confirm]** block
is a decision. At signing it is adopted as recommended unless Ajai writes a different choice into
it. After the tag, any change is a deviation and goes in §9.

- Draft date: 2026-10-25. The code it binds is listed by blob in §8.2 (authoritative over any commit id).
- Evidence the decisions rest on: [`docs/power.md`](../power.md) ("the power check": 2025–26,
  exploratory) and [`SCOPING.md`](../../SCOPING.md) (literature and data access).
- Nothing in this plan, or estimated under it, is betting or investment advice.

---

## Decisions for Ajai

Read this first. Each line gives the recommendation, then the alternative.

1. **D1 Confirmatory family** (§2). Recommended: **one confirmatory hypothesis, H1 (Kalshi), at
   α = 0.05**; Polymarket's equivalence (H2) is secondary. Its power is only about 0.58–0.74 if
   about 70% of the season is left at signing (power check, equivalence table). Alternative:
   H1 and H2 both confirmatory under Holm (first step 0.025), which lowers H1's power at a 70%
   window from 0.97 to 0.93.
2. **D2 Equivalence margin** (§2.1). Recommended: **δ = 0.002 nats per match**, about the gap
   between the bookmaker-average close and Betfair in 2025–26 (−0.0022 ± 0.0005). Reading:
   "Kalshi is within the distance that separates ordinary bookmakers from the exchange."
   Alternatives: 0.0015 (stricter, lower power) or 0.003 (easier to pass, a weaker claim).
3. **D3 Read time** (§1.3). Recommended: **the last Kalshi minute candle at or before kickoff**
   as primary, and 60 minutes before kickoff as a pre-registered robustness read (R2).
   Timing didn't move RQ1 in 2025–26 (paired change +0.0005 ± 0.0008). Alternative: −60 minutes
   as primary, closer to Betfair's snapshot, at the cost of a little more se.
4. **D4 Kalshi price** (§1.3). Recommended: **the mid of yes-bid and yes-ask**, falling back
   to the candle's last trade when the book is one-sided or the spread is over 10 cents. The
   share of fallbacks is reported. Alternative: last trade throughout.
5. **D5 De-vigging** (§1.3). Recommended: **proportional** (each of the three prices divided by
   their sum) for every source, with Shin's method as robustness R3. Alternative: Shin primary.
6. **D6 Clustering** (§2.2). Recommended: **CR1 by division × ISO week**. Alternative: by
   division × calendar date (finer clusters, smaller se).
7. **D7 League list** (§1.2). Recommended: **the 18 leagues in `src/sharpmkt/config.py`**. A
   venue's fixture counts wherever that venue lists the match, so coverage it adds in 2026–27
   inside those leagues counts. Alternative: freeze each venue's 2025–26 league coverage.
8. **D8 Window and data pull** (§1.1). Recommended: **league fixtures kicking off after the
   `pap-v1` tag time and on or before 2027-06-30**, with one data pull on or after 2027-07-01.
9. **D9 Minimum-sample rule** (§2.3). Recommended: if fewer than **1,500** Kalshi fixtures are
   paired with Betfair, H1 is reported as exploratory. At 1,500 the expected se is about
   0.00066, giving power of about 0.83 at α = 0.05. Alternative: no floor.
10. **D10 Disclosures** (§0.3). Ajai to state whether they hold, or have held, accounts or
    positions on Kalshi, Polymarket or Betfair, and whether they will trade on them during the
    window.

---

## 0. Status, conventions, disclosures, protocols

### 0.1 Signature

*Unsigned.* To sign: state which decisions are adopted as recommended and which are changed. The
plan is then frozen with the annotated tag `pap-v1`, and the tag's time is T0, the start of the
confirmatory window.

### 0.2 Conventions

- **Exploratory season:** 2025–26 (matches kicking off 2025-07-01 to 2026-06-30). All of it has
  been looked at, and the plan was written with that knowledge. Every 2025–26 estimate is
  exploratory, wherever it appears.
- **Confirmatory sample:** league matches kicking off after T0 and on or before 2027-06-30
  (D8). **None of them had happened when the plan was written**, so the outcome data couldn't
  have been seen.
- "Venue" means Kalshi or Polymarket. "Betfair" means the Betfair Exchange closing odds
  published by football-data.co.uk (columns `BFECH`, `BFECD`, `BFECA`).
- Log scores are in nats. d > 0 means the venue was more accurate than Betfair.

### 0.3 Disclosures

- The code, analysis and drafts are produced with Claude (Anthropic), running in Claude Code
  under Ajai's direction. Ajai sets the research questions, signs the plan and approves every
  deviation.
- Exploratory knowledge: the hypothesis direction (equivalence, not superiority) was chosen
  after seeing that 2025–26's Kalshi−Betfair difference was −0.0003 ± 0.0004. That's why H1 is an
  equivalence test with a margin fixed in advance, rather than a test of "no difference".
- **[PROPOSED — Ajai to confirm]** Financial interests: none in Kalshi, Polymarket, Betfair or
  any bookmaker. No positions held or traded during the confirmatory window (D10).

### 0.4 Protocols for the confirmatory run

- **P1 Single run.** The confirmatory script is `src/sharpmkt/confirm.py`. It was tested on
  2025–26 (§8.3) and its git blob hash is in §8.2. It runs **once**, after the window closes,
  and it does the 2026–27 data pull itself, after its marker exists, so the pull is the first
  read. Before reading anything it refuses unless:
  - (a) `pap-v1` is an annotated tag;
  - (b) HEAD descends from it;
  - (c) every file under `src/`, plus `pyproject.toml` and `uv.lock`, is byte-identical to its
    blob at `pap-v1`, which covers the script and every module it imports;
  - (d) nothing under them is modified or untracked, so no added file can shadow bound code;
  - (e) the window has closed (the run date is after 2027-06-30).
- **P1a Season lock.** Every pipeline entry point (`footballdata`, `kalshi`, `polymarket`,
  `match`, `panel`) refuses to run on 2026–27 (`SHARPMKT_SEASON=2627`) unless the confirmatory
  run's token is set. The script sets it only after its checks pass and its marker exists. This
  prevents accidental reads; it doesn't prevent deliberate ones, so P1–P3 and the git record
  remain the real guarantee.
- **P2 Window guard.** The script keeps only fixtures whose football-data kickoff is after T0
  (read from the tag) and on or before 2027-06-30. It records the count before and after the
  filter.
- **P3 Attempt marker.** The script creates `docs/results/confirmatory.attempt` (UTC time,
  HEAD) by exclusive creation before it reads outcome data. Its output, whether a result or a
  traceback, goes to `docs/results/confirmatory.md`. Both are committed **unedited**, in a commit
  containing only those files. While the marker exists, the script refuses to run again.
- **P4 Refusals and failures.** A refusal before the marker means nothing was read; the fix is
  logged in §9 with Ajai's approval. A failure after the marker is an attempt, not a result. A
  rerun needs a §9 entry and Ajai's approval, the attempt record stays, and the hypothesis is
  reported with that history.
- **P5 Demotion.** A deviation adopted after a confirmatory result has been seen demotes that
  hypothesis to exploratory. The pre-registered specification is still reported as the primary
  result.

---

## 1. Data and measurement

### 1.1 Sources and window

| source | what | access |
|---|---|---|
| football-data.co.uk, season `2627`, one CSV per division | fixtures, kickoff (UK time → UTC), full-time result, Betfair Exchange closing odds, market-average closing odds | free CSV |
| Kalshi public API (`/historical/markets`, `/historical/markets/{ticker}/candlesticks`, and the live equivalents) | settled match-winner markets (home, away, tie) and minute candles over the 180 minutes before kickoff | no key |
| Polymarket Gamma + CLOB APIs (`/events?series_id=`, `/prices-history`) | closed match events (two "Will X win on DATE?" markets and one draw market) and per-minute price history over the 180 minutes before kickoff | no key |

Pinnacle closing odds aren't in football-data's 2026–27 files, so Pinnacle is not used.
Every response is cached, and its URL and SHA-256 go into `data/raw/MANIFEST.json`, as for
2025–26.

### 1.2 Fixtures and matching

- **Leagues:** the 18 divisions listed in `config.LEAGUES` (D7). Only fixtures in football-data's
  division files count: cup ties and playoffs the files don't carry are out.
- **Matching:** `sharpmkt.match`, unchanged from 2025–26. Candidates are fixtures in the same
  division within a day of the venue's date. Team names are compared after normalisation, and
  the event is assigned to the best fixture if the summed similarity is ≥ 1.0 and beats the
  runner-up by ≥ 0.15. Polymarket events must have exactly the three full-time result markets.
- **Exclusions,** each counted and reported:
  - fixtures with no H/D/A result;
  - venue settlement disagreeing with football-data's result;
  - no Betfair closing odds;
  - no venue price at the read time.
  When a venue lists one fixture twice, the event with more volume is kept.

### 1.3 Probabilities

- **Betfair:** 1/odds for H, D and A, divided by their sum (D5).
- **Kalshi:** for each of the three markets, the last minute candle ending at or before kickoff
  (D3). The price is the mid of the candle's closing yes-bid and yes-ask, or its last trade when
  the bid is 0, the ask is 1 or the spread is over 0.10 (D4). The three prices are divided by
  their sum.
- **Polymarket:** the last price-history point at or before kickoff for each market's Yes
  token, divided by the three-price sum.

---

## 2. Hypotheses

### 2.1 Confirmatory: H1

**H1. At kickoff, Kalshi's match probabilities are as accurate as the Betfair Exchange closing
line, to within δ = 0.002 nats per match (D2).**

For each fixture i priced by both,

    d_i = log p_Kalshi,i(result_i) − log p_Betfair,i(result_i).

- **Estimate:** the mean of d_i over fixtures.
- **Null hypothesis (non-equivalence):** |E[d]| ≥ δ.
- **Test:** two one-sided tests at α = 0.05 each. Equivalence is declared if and only if the
  90% confidence interval of the mean, with the clustered se of §2.2, lies inside (−0.002,
  +0.002).
- **Reported alongside:** the mean, its 95% CI, and the conventional two-sided test of
  E[d] = 0. That test is not confirmatory.

### 2.2 Inference

The se is CR1 cluster-robust by division × ISO week of kickoff (D6), using
`sharpmkt.power.cluster_se`. In 2025–26 the clustered and iid se agree to within 15%.

### 2.3 Minimum sample (D9)

If fewer than 1,500 fixtures are paired, H1 is reported as exploratory, with the reason stated.

### 2.4 Power

In 2025–26 the se was 0.00044 over a full season (3,426 fixtures). Assuming true d = 0, H1's
power at α = 0.05 is 0.97 if 70% of a season is left at T0, 0.94 at 60% and 0.78 at 40%.
If true d equals the 2025–26 estimate (−0.0003), power is a little lower. That should be stated in
the paper.

### 2.5 Secondary: H2 (D1)

H2 is the same test for Polymarket. It's reported with its own 90% CI and labelled secondary,
because of its power (about 0.74 at 70% of a season).

---

## 3. Robustness (reported beside H1, none of them confirmatory)

- **R1 Brier score** in place of the log score (Betfair minus venue, so > 0 still means the
  venue is better).
- **R2 Read time.** Kalshi read 30, 60 and 120 minutes before kickoff, on the fixtures priced at
  every offset (D3).
- **R3 Shin de-vigging** for every source.
- **R4 No fallback.** Fixtures where any Kalshi market used the last-trade fallback are dropped.
- **R5 Top five leagues only** (E0, D1, I1, SP1, F1).
- **R6 Bookmaker-average yardstick.** The same paired comparison for the market-average close
  against Betfair, as the scale for δ.
- **R7 Clusters by division × date.**

---

## 4. Exploratory (labelled exploratory wherever they appear)

- **X1 (RQ3) Timing and calibration.** For each venue, at read times 0, 30, 60 and 120 minutes
  before kickoff:
  - the calibration-slope gap to Betfair, from a stacked logit of outcome on logit
    probabilities with a separate intercept and slope per source, se clustered as in §2.2;
  - the venue's own slope.
  2025–26 pattern, to be described again in 2026–27: the kickoff gap is negative (−0.018
  Kalshi, −0.012 Polymarket) and shrinks at earlier reads (Polymarket's vanishes). That points
  to late information, not bias. Kalshi's remaining gap at −60 minutes is reported with its MDE
  (about 0.014 over a full season), not as a test.
- **X2 Favourite–longshot returns.** Return to a unit stake at each venue's normalised price,
  by price bucket (<0.10, 0.10–0.25, 0.25–0.50, 0.50–0.75, ≥0.75), before fees.
- **X3 (RQ4) Liquidity and division.** OLS of d on the venue's standardised log volume and a
  top-five dummy, clustered. Also the mean d by division.
- **X4 (RQ2) Encompassing, Polymarket.** The logarithmic opinion pool weight on Polymarket with
  Betfair alongside. Not run for Kalshi: it's uninformative there, because the two venues' prices
  are almost collinear (2025–26 MDE 1.8).

---

## 5. What would change the plan before signing

- Kalshi or Polymarket changing their APIs so that 2026–27 can't be read the same way. The
  season lock (P1a) blocks the pipeline on 2026–27, so a check before signing must touch only
  API metadata, such as series listings and endpoint shapes, and never results or prices. That
  check is logged as a deviation if it is done after T0.
- football-data dropping Betfair closing odds for 2026–27. Its current files have them.

## 6. Timeline

| date | step |
|---|---|
| before signing | ~~write and test `confirm.py` on 2025–26; record its blob hash~~ done (§8.2, §8.3); re-record the hashes if any code changes before the tag |
| T0 (signing) | tag `pap-v1`; the confirmatory window opens |
| 2027-06-30 | window closes |
| on or after 2027-07-01 | one data pull, then one confirmatory run (P1–P3) |

## 7. Data already used (exploratory)

`data/raw/MANIFEST.json` at `47169eb` covers every 2025–26 file and API response.

## 8. Code

### 8.1 Pipeline

`sharpmkt.footballdata` → `sharpmkt.kalshi markets` / `sharpmkt.polymarket markets` →
`sharpmkt.match` → `sharpmkt.kalshi prices` / `sharpmkt.polymarket prices` → `sharpmkt.panel`,
all run on 2026–27 by `sharpmkt.confirm` (P1), which then writes `docs/results/confirmatory.md`.

### 8.2 Bound blobs (draft, 2026-10-25)

The tag binds every file under `src/` plus `pyproject.toml` and `uv.lock` (P1c). The blobs at the
time of this draft are below. They must match `git rev-parse pap-v1:<path>` at signing. If any
file changes before the tag, this table is re-recorded at signing.

| path | git blob (SHA-1) |
|---|---|
| `pyproject.toml` | `a4101ea0a38ba4309264eea45b1338768c035e35` |
| `src/sharpmkt/__init__.py` | `932689079c624895ff0682af4d0611844235c323` |
| `src/sharpmkt/config.py` | `efbb2f7d1837beb67f838f23fa99e2bac5cbd379` |
| `src/sharpmkt/confirm.py` | `8608c0cd19fff98e97675a03ff9bffc1854899e4` |
| `src/sharpmkt/estimators.py` | `7c035458df62c7445701f187b50d1a21f3657c20` |
| `src/sharpmkt/footballdata.py` | `9e85248a01d2bb1f3815ff1b5b8e361d913a9ef6` |
| `src/sharpmkt/http.py` | `8f2717f00f1c211f7510ba4ff1481571c26150b0` |
| `src/sharpmkt/kalshi.py` | `c6aef041a2ea32e2f783abb35c010de0a01fe36f` |
| `src/sharpmkt/match.py` | `c30c510db04bae893fd8e626d0c2260f058a6782` |
| `src/sharpmkt/panel.py` | `4643407c9fa2ee325acdc49bd729ee18760d1cb4` |
| `src/sharpmkt/polymarket.py` | `13b9fe91c36f670408062b0c68c1dccccee8ab8f` |
| `src/sharpmkt/power.py` | `c5a1d90b5fee01b49fb8cd81545a6dd1c03dd7aa` |
| `src/sharpmkt/py.typed` | `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391` |
| `uv.lock` | `76ee3702c74129cf9d5a4442b5d29a8fe1b11abe` |

### 8.3 Test of the script on 2025–26

`uv run python -m sharpmkt.confirm --dry-run 2025-12-01` runs the window guard and the full
analysis (§2–§4) on the exploratory season, with no binding, marker or date guard, writing
[`docs/results/dryrun_2526.md`](../results/dryrun_2526.md). The dry run refuses the
confirmatory season. On a December-to-June window (about 60% of the season) it gives:
- **H1 Kalshi:** 2,592 matches, mean d +0.00002, se 0.00053, 90% CI [−0.00086, +0.00090],
  TOST p = 0.0001, equivalent.
- **H2 Polymarket:** mean −0.00116, 90% CI [−0.00198, −0.00035], equivalent but only just.
- **R6 bookmaker-average yardstick:** −0.00223, not equivalent, as expected for the scale.
- **R2 at −60 minutes:** not equivalent (se 0.00099). The earlier read is noisier against
  Betfair's close.
These are exploratory numbers that show the script works. They aren't results.

`tests/test_confirm.py` checks each guard:
- the tag must exist and be annotated;
- changed, untracked or post-tag files are refused;
- HEAD must descend from the tag;
- the date guard;
- the single-use marker and write-once output;
- the strict window;
- the TOST;
- the season lock on every pipeline module.

## 9. Deviations

*None (draft).*
