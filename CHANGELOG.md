# Changelog

## 0.1.0 — 26 October 2026

First release.

- `rate()`, `rate_info()`, `rates(group=…)`, `groups()` — 99 verified constants, each with its unit, effective date, government source and verification date.
- `tax_slabs(regime, year)`, `exempt_limit(age_band)`, `surcharge()` — income-tax bands for both regimes.
- `professional_tax(state, salary, gender=…)`, `pt_states()`, `pt_free_states()` — 22 states that levy it, 14 that do not.
- `due_dates()` — the compliance calendar's next dates.
- `verified_on()`, `attribution()` — provenance, so a published figure can be traced.
- Standard library only. Six-hour disk cache; a stale cached copy is served if the network is down.
