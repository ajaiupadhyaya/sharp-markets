# Are Prediction Markets Sharp?

Do Kalshi and Polymarket price European football matches as well as the Betfair Exchange
closing line? Match-winner (home / draw / away) prices just before kickoff, compared with
Betfair's closing odds on the same fixtures, across the 18 leagues that football-data.co.uk,
Kalshi and Polymarket all cover.

**Status: pre-analysis plan signed and tagged `pap-v1` (2026-10-25).** The confirmatory sample
is the 2026–27 matches kicking off after the tag time, through 2027-06-30. They are read once,
by `uv run python -m sharpmkt.confirm`, after the window closes. Until then, every pipeline
module refuses the 2026–27 season.

- `SCOPING.md`: prior literature, data access and the draft design.
- `docs/power.md`: the 2025–26 power check.
- `docs/pap/pre-analysis-plan.md`: the signed pre-analysis plan.
- `docs/results/dryrun_2526.md`: the confirmatory script's test run on 2025–26 (not a result).

```bash
make all   # every step: fixtures, venue markets, matching, kickoff prices, panel, power, tests
```

Nothing raw is committed. `data/raw/MANIFEST.json` records the URL, SHA-256 and size of every
API response and CSV that was used.
