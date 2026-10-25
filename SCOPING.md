# Are Prediction Markets Sharp? — scoping memo

Working title for a study of whether the new sports prediction markets (Kalshi, Polymarket)
price European football as well as the sharpest bookmaker and betting exchange closing lines.
It's built like the earlier projects: a plan signed before the confirmatory data exists, a raw
data manifest, and an AEA-style replication package.

Status: scoping only (2026-10-25). Data access has been checked, with one match pulled from each
source to confirm prices line up. Nothing has been estimated.

## 1. Why this, and not plain "calibration"

Plain calibration of Polymarket or Kalshi is already crowded: five papers in the last year cover
it (section 2). The open question is a **benchmark**. Every one of those papers compares prices
with realised frequencies, and none compares them with the market that has priced sport longest
and best: the bookmaker and exchange **closing line**. Since mid-2025, sport has been the
majority of prediction-market volume (Pew, Sep 2026). So it's a live question, with real money
behind it, whether a regulated US event-contract exchange prices a Serie B match as well as
Pinnacle or Betfair.

It also avoids the Italy study's problem. There are thousands of independent matches, and the
comparison is **paired** within each match (the same outcome priced by two venues at the same
moment), so match-level noise cancels.

## 2. Prior literature (checked 2026-10-25)

| Paper | What it does | What it leaves open |
|---|---|---|
| Bürgi, Deng & Whelan, "Makers and Takers: The Economics of the Kalshi Prediction Market" (CESifo WP 12122, 2025; UCD 2026) | All Kalshi contracts: prices fairly accurate, more so near close; favorite–longshot bias (FLB); takers lose ~32%, makers ~10% | No sportsbook benchmark |
| Cardozo & Rivero-Wildemauwe, arXiv 2609.12878 (Sep 2026) | Polymarket, 588M trades: two-sided FLB in crypto and politics, **absent in sports**; results flip with how contracts are grouped | No Kalshi, no bookmaker benchmark |
| Moshrefi, arXiv 2607.14430 (Jul 2026) | Kalshi sports, 23M moneyline trades: calibration step-like in the last 10 minutes; parlays overpriced | Against realised outcomes only |
| arXiv 2602.19520 | Polymarket calibration by domain and horizon (sports reliable under a week, biased beyond a month) | No benchmark |
| arXiv 2610.13593 | Time-varying FLB in Polymarket weather markets | Different domain |
| Diercks, Katz & Wright, "Kalshi and the Rise of Macro Markets" (FEDS 2026-010 / NBER w34702) | Kalshi macro markets against fed funds futures and surveys | **This is the template**: a benchmark comparison, but for macro, not sport |
| Ng, Peng, Tao & Zhou, "Price Discovery and Trading in Modern Prediction Markets" (SSRN 5331995) | Polymarket vs Kalshi lead-lag; Kalshi leads in sports | Venue vs venue, not vs bookmakers |
| arXiv 2601.01706, "Semantic Non-Fungibility…" | Law of one price across 10 venues, 2–4% deviations | Arbitrage, not accuracy |
| Kanoria, Ma, Sethi & Sirolly, "Network-Based Detection of Wash Trading" (SSRN, Nov 2025) | ~25% of Polymarket volume is wash trading | Means Polymarket's volume is a poor liquidity measure |

**Gap:** two searches found no academic paper testing Kalshi or Polymarket sports prices against
a bookmaker or exchange closing line. The nearest is a practitioner blog (OddsPapi, 88
fixtures). Recheck before signing: this field moves monthly.

## 3. Data access — checked

| Source | Access | What it gives | Checked |
|---|---|---|---|
| **Kalshi** public API (`api.elections.kalshi.com/trade-api/v2`) | No key needed for market data | Settled match markets (home / away / tie) for ~300 "GAME" series, every top-two European division. Minute candlesticks with bid, ask and last price, plus individual trades. Markets older than a few months live under `/historical/...` | ✅ EPL: 462 settled matches since 2025-08-15. Liverpool–Bournemouth draw at kickoff: bid 0.13, ask 0.15, 89,744 contracts open |
| **Polymarket** Gamma + CLOB APIs | No key | Closed events, three markets per match; `prices-history` per outcome token. It **needs explicit `startTs`/`endTs`**: `interval=max` returns nothing for resolved markets | ✅ Bournemouth–Man City, 432 ten-minute points in the last 3 days |
| **football-data.co.uk** | Free CSVs, ~22 leagues | Results plus pre-closing and **closing** 1X2 odds: Bet365, market max and average, **Betfair Exchange** (both seasons), **Pinnacle** (2025–26 only) | ✅ 2025–26 EPL has PSC* and BFEC*; 2026–27 has BFEC* but no Pinnacle columns |

Sanity check on one match (Liverpool–Bournemouth, 2025-08-15): Pinnacle's closing, de-vigged
draw probability is 0.148 (overround 3.0%); Kalshi's draw at kickoff is 0.13 bid / 0.15 ask.
They agree to within the spread.

Caveats to plan around:
1. **Pinnacle disappears in 2026–27.** football-data stopped carrying it. **Betfair Exchange
   closing** is in both seasons, so it's the benchmark that runs through the whole sample, and
   it's an exchange like Kalshi, which is the cleaner comparison. Pinnacle is a 2025–26
   robustness check.
2. **"Closing" timestamps differ.** football-data's closing odds are collected near kickoff,
   not to the second. Kalshi and Polymarket prices must be taken at a matched moment, for
   example the last trade or mid-price before kickoff. Kickoff times come from football-data
   (UK time) and must be converted.
3. **Kalshi markets close early** once the result is known. Use pre-kickoff prices only, never
   in-play.
4. **Draws.** Kalshi lists "TIE" as its own market. The three Kalshi prices don't sum to 1 (the
   spread), so normalise them the same way bookmaker odds are de-vigged, using two methods
   (proportional and Shin) as robustness.
5. **Volume measures.** Kalshi reports contracts; Polymarket's volume is partly wash trading
   (about 25%), so don't use it as a liquidity measure without care.
6. **Terms.** Check both APIs' terms of use for research use and redistribution. The likely
   answer is: redistribute nothing raw, commit only a manifest, as before.

## 4. Research questions (draft — for you to set)

- **RQ1 — Accuracy.** At kickoff, are Kalshi's (and Polymarket's) match probabilities as
  accurate as the Betfair Exchange closing line? Measure: paired difference in log score (and
  Brier) per match.
- **RQ2 — Information.** Does Kalshi's price carry information the closing line doesn't?
  Encompassing test: a multinomial logit of the result on both venues' log-odds. If the closing
  line encompasses Kalshi, Kalshi's coefficient is 0.
- **RQ3 — Favorite–longshot bias.** Does Kalshi football show the FLB that Bürgi et al. find
  across Kalshi, or its absence, as Cardozo & Rivero-Wildemauwe find for Polymarket sports? And
  is it larger than the bookmakers' own FLB?
- **RQ4 — Where the gaps are.** Do accuracy gaps shrink with Kalshi liquidity (open interest,
  spread), in top divisions compared with second divisions, and over time as volume grew
  through 2025–26?
- **RQ5 (optional, finance angle).** Does a simple rule (buy on Kalshi when it is cheaper than
  the exchange's de-vigged price by more than the fee) make money after Kalshi's fee schedule?
  This tests whether the inefficiency in RQ1 is exploitable. It's research, not advice.

## 5. Design sketch

**Sample split, decided before anything is estimated:**
- **Exploratory:** 2025–26 season, all leagues covered by both Kalshi and football-data. Use
  it to fix definitions (timing, de-vigging, league list), run the power check and draft the
  plan.
- **Confirmatory:** every 2026–27 match that kicks off **after the plan is signed**, through
  the end of the season (May 2027). These matches haven't happened yet, which makes this the
  strongest form of pre-registration: the outcome data can't have been seen. That also fits
  your timeline (you graduate in May 2027).

**Unit:** a match, with three outcomes priced by each venue, giving ~6,000+ matches in 2025–26
across ~20 leagues (to be counted).

**Inference:** match-level paired differences, clustered by matchday × league, because games
on the same weekend share shocks. Diebold–Mariano-style tests on log-score differences.

**Power:** check on 2025–26 before signing. The paired design should give much better power
than the Italy study, but the check decides, not the intuition.

## 6. Decisions that are yours

1. **Scope:** Kalshi only, or Kalshi plus Polymarket? Polymarket adds a second venue but costs
   effort, and its volume is noisy because of wash trading.
2. **Sport:** football only (free closing lines), or US sports too? US closing lines aren't
   free, so I'd say football only.
3. **Primary benchmark:** Betfair Exchange closing (both seasons), with Pinnacle as a 2025–26
   check.
4. **Whether RQ5 (the trading rule) is in.** It's the finance-facing piece, but it adds a fee
   model and execution assumptions.
5. **The confirmatory window:** the plan's signing date through May 2027.

## 7. Rough size

Kalshi: about 3 markets × 6,000+ matches, minute candles for the last few hours before kickoff.
That's tens of thousands of small API calls, so it needs throttling and caching, but the data is
small (MBs). football-data: about 40 CSVs. Polymarket: a similar call count if included. All of
it runs on a laptop, and none of it needs the 26 GB of free disk.
