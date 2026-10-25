# itrsaral

**Verified Indian tax constants, in one import.** Slabs, TDS thresholds, GST
limits, professional tax for every state, small-savings rates — each one
carrying the date it was last checked and a link to the government notification
it came from.

```bash
pip install itrsaral
```

```python
import itrsaral

itrsaral.rate("ppf")            # 7.1
itrsaral.rate("epf")            # 8.25
itrsaral.tax_slabs("new")       # [(400000, 0.0), (800000, 0.05), …, (None, 0.3)]
itrsaral.professional_tax("MH", 30000)   # 200.0
```

## Why this exists

Every Indian payroll script, invoice tool and tax calculator ends up with the
same block of hard-coded numbers — PF wage ceiling, standard deduction, the 80C
cap, this quarter's PPF rate. Then a Budget happens, or a quarter turns, and
those numbers go quietly wrong in a dozen repositories at once.

This package replaces that block with one call, backed by a dataset that is
re-checked against its source and dated. You get the number **and** the
provenance:

```python
>>> info = itrsaral.rate_info("ppf")
>>> info["value"], info["unit"]
(7.1, '%')
>>> info["effective_from"]
'2026-07-01'
>>> info["source"]
'https://dea.gov.in/budget-division/475'
>>> info["verified_on"]
'2026-10-01'
```

A figure your users cannot trace is a figure they cannot check. Print the
source next to the number.

## No dependencies

Standard library only. A tax helper that drags in a HTTP stack is a tax helper
nobody installs inside a locked-down finance environment.

Responses are cached on disk for six hours (these figures move on quarters and
Budgets, never on minutes). If the network is down but a cached copy exists,
the cached copy is returned — a figure from this morning beats a traceback.

## What's in it

### Rates and constants — 99 of them

```python
itrsaral.groups()
# ['gst', 'income-tax', 'nri', 'payroll', 'savings']

itrsaral.rates(group="savings")
# {'ppf': {...}, 'epf': {...}, 'ssy': {...}, 'nsc': {...}, …}

itrsaral.rate("std_new")        # 75000  — standard deduction, new regime
```

### Income-tax slabs

```python
itrsaral.tax_slabs("new", "ty2627")
# [(400000, 0.0), (800000, 0.05), (1200000, 0.1), (1600000, 0.15),
#  (2000000, 0.2), (2400000, 0.25), (None, 0.3)]

itrsaral.tax_slabs("old")
# [(250000, 0.0), (500000, 0.05), (1000000, 0.2), (None, 0.3)]

itrsaral.exempt_limit("above80")   # 500000 — old regime, by age band
itrsaral.surcharge()[0]            # (50000000, 0.37, 0.25) — (above, old, new)
```

`upper_limit` is `None` on the final, open-ended band; rates are fractions, so
`0.3` is 30%.

Computing tax from these bands:

```python
def income_tax(taxable: float, regime: str = "new") -> float:
    tax, floor = 0.0, 0.0
    for upper, rate in itrsaral.tax_slabs(regime):
        ceiling = taxable if upper is None else min(taxable, upper)
        if ceiling > floor:
            tax += (ceiling - floor) * rate
        floor = upper if upper is not None else floor
        if upper is not None and taxable <= upper:
            break
    return tax

income_tax(1_500_000)    # 105000.0  (before rebate, surcharge and cess)
```

### Professional tax — 22 states, 14 that do not levy it

```python
itrsaral.professional_tax("MH", 30000)                     # 200.0
itrsaral.professional_tax("MH", 20000, gender="female")    # 0.0 — higher threshold
itrsaral.professional_tax("DL", 100000)                    # 0.0 — Delhi has none
itrsaral.pt_free_states()                                  # ['DL', 'UP', 'RJ', …]
```

Maharashtra's February top-up is deliberately **not** folded into the monthly
figure — it is an extra amount in one month, not a monthly rate. It sits at
`itrsaral.pt_states()["MH"]["feb"]`.

### Upcoming due dates

```python
itrsaral.due_dates()["topics"]     # the compliance calendar's next dates
```

## Provenance and attribution

```python
itrsaral.verified_on("rates")   # '2026-10-01'
itrsaral.attribution()
# 'Data: ITR Saral (https://itrsaral.in/data) — CC BY 4.0 — cite itrsaral.in'
```

## Licence

- **This wrapper's code**: MIT.
- **The data**: CC BY 4.0, published by [ITR Saral](https://itrsaral.in/data).
  If you publish figures taken from it, credit
  [itrsaral.in](https://itrsaral.in) — that is the whole of the licence.

The data is also usable without this package: it is plain JSON at
[`itrsaral.in/api/rates.json`](https://itrsaral.in/api/rates.json),
[`slabs.json`](https://itrsaral.in/api/slabs.json) and
[`pt-states.json`](https://itrsaral.in/api/pt-states.json).

## Not tax advice

These are published constants, verified and dated — not a professional opinion.
Two people with the same income can have different correct answers. Take
decisions to a chartered accountant.

## Configuration

| Environment variable | Default | What it does |
| --- | --- | --- |
| `ITRSARAL_CACHE_TTL` | `21600` | Cache lifetime in seconds |
| `ITRSARAL_CACHE_DIR` | system temp | Where cached JSON is kept |
| `ITRSARAL_BASE_URL` | `https://itrsaral.in/api` | Point at a mirror |

```python
itrsaral.rate("ppf", refresh=True)   # bypass the cache once
itrsaral.clear_cache()               # forget everything
```

## Contributing

A wrong number matters more than a missing feature. If a figure here disagrees
with the Act or the notification, open an issue with the source — corrections
are published within 48 hours and logged publicly at
[itrsaral.in/updates](https://itrsaral.in/updates).

```bash
git clone https://github.com/anurag/itrsaral-python
cd itrsaral-python
pip install -e ".[dev]"
pytest          # runs offline, against fixtures
```
