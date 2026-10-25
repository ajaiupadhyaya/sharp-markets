# Are Prediction Markets Sharp?

Do Kalshi and Polymarket price European football matches as well as the Betfair Exchange
closing line? Match-winner (home / draw / away) prices just before kickoff, compared with
Betfair's closing odds on the same fixtures, across the 18 leagues that football-data.co.uk,
Kalshi and Polymarket all cover.

**Status: exploratory season (2025–26) pulled; power check run.** The confirmatory sample will
be 2026–27 matches that kick off after the pre-analysis plan is signed.

- `SCOPING.md`: prior literature, data access and the draft design.
- `docs/power.md`: the 2025–26 power check.
- `docs/pap/pre-analysis-plan.md`: the DRAFT pre-analysis plan (unsigned).

```bash
make all   # every step: fixtures, venue markets, matching, kickoff prices, panel, power, tests
```

Nothing raw is committed. `data/raw/MANIFEST.json` records the URL, SHA-256 and size of every
API response and CSV that was used.
