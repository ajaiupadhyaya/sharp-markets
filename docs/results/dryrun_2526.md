# DRY RUN on 2025-26 (exploratory season, not a result)

Window: kickoff after 2025-12-01T00:00:00+00:00 and at or before 2026-06-30T23:59:59+00:00. Fixtures with Betfair closing odds: 6171 in the season, 3646 in the window.

## H1 (confirmatory): Kalshi vs Betfair Exchange closing, log score

| test | matches | clusters | mean d | se (clustered) | 90% CI | TOST p | equivalent within ±0.002 | p (mean = 0) |
|---|---|---|---|---|---|---|---|---|
| H1 Kalshi | 2592 | 270 | +0.00002 | 0.00053 | [-0.00086, +0.00090] | 0.0001 | yes | 0.966 |

**H1 is supported:** Kalshi is within ±0.002 nats per match of the Betfair Exchange close (TOST p = 0.0001, α = 0.05).

## H2 (secondary): Polymarket vs Betfair

| test | matches | clusters | mean d | se (clustered) | 90% CI | TOST p | equivalent within ±0.002 | p (mean = 0) |
|---|---|---|---|---|---|---|---|---|
| H2 Polymarket | 2817 | 284 | -0.00116 | 0.00050 | [-0.00198, -0.00035] | 0.0461 | yes | 0.019 |

## Robustness (not confirmatory)

| test | matches | clusters | mean d | se (clustered) | 90% CI | TOST p | equivalent within ±0.002 | p (mean = 0) |
|---|---|---|---|---|---|---|---|---|
| R1 Brier score (Kalshi) | 2592 | 270 | +0.00005 | 0.00034 | [-0.00050, +0.00061] | 0.0000 | yes | 0.880 |
| R2 Kalshi read 30 min before kickoff | 2583 | 270 | +0.00012 | 0.00066 | [-0.00096, +0.00120] | 0.0021 | yes | 0.851 |
| R2 Kalshi read 60 min before kickoff | 2561 | 270 | -0.00068 | 0.00099 | [-0.00231, +0.00094] | 0.0911 | no | 0.488 |
| R2 Kalshi read 120 min before kickoff | 2422 | 270 | -0.00113 | 0.00108 | [-0.00290, +0.00064] | 0.2084 | no | 0.295 |
| R3 Shin de-vigging (Kalshi) | 2592 | 270 | -0.00009 | 0.00057 | [-0.00103, +0.00084] | 0.0004 | yes | 0.868 |
| R4 Kalshi, no last-trade fallback | 2591 | 270 | +0.00002 | 0.00053 | [-0.00086, +0.00090] | 0.0001 | yes | 0.971 |
| R5 Kalshi, top five leagues | 1004 | 102 | +0.00027 | 0.00070 | [-0.00087, +0.00142] | 0.0066 | yes | 0.696 |
| R6 bookmaker average vs Betfair (yardstick) | 3645 | 359 | -0.00223 | 0.00071 | [-0.00340, -0.00106] | 0.6253 | no | 0.002 |
| R7 Kalshi, clusters by division x date | 2592 | 836 | +0.00002 | 0.00053 | [-0.00085, +0.00089] | 0.0001 | yes | 0.966 |

R4 drops 1 fixtures that used Kalshi's last-trade fallback.

## Exploratory (labelled exploratory wherever they appear)

### Timing control: the venue read earlier

Each venue read at kickoff and 30 / 60 / 120 minutes before it, from the same fetched candles, on the fixtures it priced at every offset. Betfair's closing snapshot is fixed. If the RQ3 gap and the RQ1 difference come from the venue being read later than Betfair, they should shrink or reverse at earlier offsets.

| venue | read at | fixtures | median staleness (min) | RQ1 mean d (se) | RQ3 slope gap (se) | venue slope (se) |
|---|---|---|---|---|---|---|
| Kalshi | kickoff | 2421 | 0 | -0.0001 (0.0005) | -0.016 (0.003) | 1.007 (0.047) |
| Kalshi | -30 min | 2421 | 0 | +0.0001 (0.0007) | -0.007 (0.004) | 1.016 (0.048) |
| Kalshi | -60 min | 2421 | 0 | -0.0005 (0.0010) | -0.008 (0.006) | 1.016 (0.048) |
| Kalshi | -120 min | 2421 | 1 | -0.0012 (0.0011) | -0.012 (0.006) | 1.012 (0.048) |
| Kalshi | kickoff vs -60 (paired change) | 2421 | | +0.0004 (0.0009) | | |
| Polymarket | kickoff | 2817 | 0 | -0.0012 (0.0005) | -0.016 (0.003) | 1.015 (0.046) |
| Polymarket | -30 min | 2817 | 0 | -0.0007 (0.0006) | -0.008 (0.003) | 1.023 (0.047) |
| Polymarket | -60 min | 2817 | 0 | -0.0004 (0.0009) | -0.003 (0.005) | 1.028 (0.046) |
| Polymarket | -120 min | 2817 | 0 | -0.0005 (0.0010) | -0.003 (0.006) | 1.028 (0.047) |
| Polymarket | kickoff vs -60 (paired change) | 2817 | | -0.0008 (0.0008) | | |

### RQ3: favourite-longshot bias (calibration slope)

Per outcome row (three per match): logit P(y = 1) = a + b * logit(p). b > 1: favourites under-priced and longshots over-priced (the FLB). Fitted jointly for venue and Betfair on the same rows, so the difference b_v - b_bf has a clustered se.

| venue | rows | b_v (se) | b_bf (se) | b_v - b_bf (se) | MDE for b_v - b_bf: full / 60% / 40% | MDE for b_v - 1 |
|---|---|---|---|---|---|---|
| Kalshi | 7776 | 0.992 (0.046) | 1.007 (0.047) | -0.015 (0.003) | 0.009 / 0.012 / 0.014 | 0.129 |
| Polymarket | 8451 | 1.015 (0.046) | 1.031 (0.047) | -0.016 (0.003) | 0.008 / 0.011 / 0.013 | 0.128 |

Return to a 1-unit stake at the venue's (normalised) price, by price bucket, venue rows (exploratory; ignores fees and the spread):

| venue | <0.10 | 0.10-0.25 | 0.25-0.50 | 0.50-0.75 | >=0.75 |
|---|---|---|---|---|---|
| Kalshi | -0.142 (0.221), n 249 | -0.022 (0.041), n 2170 | +0.020 (0.010), n 4093 | -0.015 (0.025), n 1092 | -0.003 (0.036), n 172 |
| Polymarket | -0.295 (0.191), n 247 | -0.029 (0.041), n 2264 | +0.019 (0.010), n 4641 | -0.007 (0.025), n 1146 | +0.011 (0.038), n 153 |

### RQ4: where the gaps are (liquidity and division)

OLS of the per-match log-score difference d (venue minus Betfair) on the venue's standardised log volume and a top-five-league dummy, clustered. MDE is for each slope (per 1 sd of log volume; top five vs the rest).

| venue | matches | slope on log volume (se) | top five minus rest (se) | MDE volume: full / 60% / 40% | MDE top five: full / 60% / 40% |
|---|---|---|---|---|---|
| Kalshi | 2592 | -0.0022 (0.0011) | +0.0038 (0.0017) | 0.0032 / 0.0041 / 0.0050 | 0.0048 / 0.0062 / 0.0075 |
| Polymarket | 2482 | +0.0013 (0.0007) | -0.0016 (0.0013) | 0.0021 / 0.0027 / 0.0033 | 0.0037 / 0.0048 / 0.0058 |

Mean d by division (exploratory):

| div | Kalshi n | Kalshi mean d (se) | Polymarket n | Polymarket mean d (se) |
|---|---|---|---|---|
| B1 | 161 | +0.0007 (0.0016) | 0 |  |
| D1 | 180 | -0.0004 (0.0020) | 177 | -0.0009 (0.0013) |
| D2 | 96 | -0.0007 (0.0021) | 159 | -0.0006 (0.0010) |
| E0 | 227 | +0.0006 (0.0012) | 228 | -0.0007 (0.0013) |
| E1 | 302 | +0.0009 (0.0012) | 291 | -0.0002 (0.0008) |
| E2 | 13 | -0.0038 (nan) | 58 | -0.0072 (0.0060) |
| EC | 0 |  | 64 | -0.0070 (0.0035) |
| F1 | 159 | +0.0020 (0.0013) | 159 | -0.0000 (0.0012) |
| F2 | 0 |  | 151 | +0.0015 (0.0027) |
| G1 | 106 | +0.0027 (0.0037) | 0 |  |
| I1 | 229 | +0.0006 (0.0017) | 229 | -0.0021 (0.0013) |
| I2 | 123 | -0.0064 (0.0057) | 221 | -0.0039 (0.0045) |
| N1 | 159 | -0.0005 (0.0016) | 158 | -0.0009 (0.0009) |
| P1 | 174 | -0.0012 (0.0025) | 173 | -0.0016 (0.0018) |
| SC0 | 127 | -0.0000 (0.0018) | 125 | -0.0014 (0.0010) |
| SP1 | 209 | -0.0011 (0.0015) | 203 | -0.0010 (0.0015) |
| SP2 | 164 | +0.0006 (0.0027) | 258 | -0.0011 (0.0006) |
| T1 | 163 | +0.0013 (0.0015) | 163 | +0.0016 (0.0009) |

### RQ2: does the venue add information beyond Betfair? (encompassing)

Logarithmic opinion pool P(o) ~ exp(b_bf log p_bf(o) + b_v log p_v(o)), fitted by maximum likelihood, clustered by division x ISO week. b_v = 0: Betfair encompasses the venue; b_bf = 0: the venue encompasses Betfair.

| venue | matches | b_bf (se) | b_v (se) | corr(b_bf, b_v) | MDE for b_v: full / 60% / 40% |
|---|---|---|---|---|---|
| Polymarket | 2817 | 2.418 (0.875) | -1.376 (0.861) | -1.00 | 2.413 / 3.115 / 3.815 |

The two log probabilities are nearly collinear, so the weights trade off (strongly negative correlation). The informative quantity is whether b_v is distinguishable from 0, not b_bf + b_v.
