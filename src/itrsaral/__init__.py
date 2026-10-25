"""Verified Indian tax constants, in one import.

Every figure here is published by ITR Saral (https://itrsaral.in/data), carries
the date it was last checked and a link to the government source it came from.
Nothing is scraped and nothing is guessed.

    >>> import itrsaral
    >>> itrsaral.rate("ppf")
    7.1
    >>> itrsaral.rate_info("ppf")["source"]
    'https://dea.gov.in/budget-division/475'

Data licence: CC BY 4.0 — if you publish figures from it, credit itsaral.in.
This wrapper's own code is MIT.
"""

from __future__ import annotations

from typing import Any, Literal

from ._client import ITRSaralError, clear_cache, fetch

__version__ = "0.1.0"

__all__ = [
    "ITRSaralError",
    "clear_cache",
    "due_dates",
    "exempt_limit",
    "professional_tax",
    "pt_states",
    "rate",
    "rate_info",
    "rates",
    "slabs",
    "tax_slabs",
    "verified_on",
]

Regime = Literal["new", "old"]
Year = Literal["fy2526", "ty2627"]


# ──────────────────────────────── rates ────────────────────────────────

def rates(*, group: str | None = None, refresh: bool = False) -> dict[str, dict]:
    """Every published constant, keyed by its short name.

    Each value is a dict with ``value``, ``unit``, ``group``, ``en``/``hi``
    labels, ``effective_from``, ``source`` and ``verified_on``.

    Pass ``group`` to narrow it — e.g. ``"savings"``, ``"tds"``, ``"gst"``.
    """
    data = fetch("rates", refresh=refresh)["keys"]
    if group is None:
        return data
    return {k: v for k, v in data.items() if v.get("group") == group}


def rate(key: str, *, refresh: bool = False) -> float | int | str:
    """Just the number, for when that is all you want.

    >>> rate("epf")
    8.25
    """
    return rate_info(key, refresh=refresh)["value"]


def rate_info(key: str, *, refresh: bool = False) -> dict[str, Any]:
    """The full record behind a constant — including where it came from.

    Reach for this instead of :func:`rate` whenever you are going to show the
    number to someone. A figure a reader cannot trace is a figure they cannot
    check.
    """
    data = fetch("rates", refresh=refresh)["keys"]
    try:
        return data[key]
    except KeyError:
        near = [k for k in data if key.lower() in k.lower()][:5]
        hint = f" Did you mean: {', '.join(near)}?" if near else ""
        raise KeyError(f"no rate named {key!r}.{hint}") from None


def groups(*, refresh: bool = False) -> list[str]:
    """The distinct ``group`` values, so you can browse what exists."""
    seen = {v.get("group") for v in fetch("rates", refresh=refresh)["keys"].values()}
    return sorted(g for g in seen if g)


# ──────────────────────────────── slabs ────────────────────────────────

def slabs(*, refresh: bool = False) -> dict[str, Any]:
    """The whole slab dataset — both regimes, both years, surcharge table."""
    return fetch("slabs", refresh=refresh)


def tax_slabs(
    regime: Regime = "new", year: Year = "ty2627", *, refresh: bool = False
) -> list[tuple[float | None, float]]:
    """Income-tax slabs as ``[(upper_limit, rate), …]``.

    ``upper_limit`` is ``None`` on the final, open-ended band. ``rate`` is a
    fraction, so 0.3 means 30%.

    ``year`` applies to the new regime only — the old regime's bands have not
    moved, so the upstream data carries one set for it and ``year`` is ignored.

    >>> tax_slabs("new", "ty2627")[0]
    (400000, 0.0)
    """
    key = "newRegime" if regime == "new" else "oldRegime"
    data = fetch("slabs", refresh=refresh)
    try:
        block = data[key]
    except KeyError:
        raise KeyError(f"no slabs for regime={regime!r}. Have: {', '.join(data)}") from None

    if "slabs" in block:                       # old regime: one set, no year
        rows = block["slabs"]
    else:                                      # new regime: keyed by year
        try:
            rows = block[year]["slabs"]
        except KeyError:
            raise KeyError(
                f"no slabs for regime={regime!r} year={year!r}. Have: {', '.join(block)}"
            ) from None
    return [(None if upper is None else upper, float(pct)) for upper, pct in rows]


def exempt_limit(
    age_band: Literal["below60", "60to80", "above80"] = "below60", *, refresh: bool = False
) -> int:
    """Old-regime basic exemption for an age band.

    The new regime has one limit for everyone, so this is old-regime only.

    >>> exempt_limit("above80")
    500000
    """
    block = fetch("slabs", refresh=refresh)["oldRegime"].get("exempt", {})
    try:
        return int(block[age_band])
    except KeyError:
        raise KeyError(
            f"unknown age band {age_band!r}. Have: {', '.join(block)}"
        ) from None


def surcharge(*, refresh: bool = False) -> list[tuple[int, float, float]]:
    """Surcharge bands as ``[(income_above, old_rate, new_rate), …]``, richest first."""
    return [tuple(row) for row in fetch("slabs", refresh=refresh)["surcharge"]]  # type: ignore[misc]


# ─────────────────────────── professional tax ───────────────────────────

def pt_states(*, refresh: bool = False) -> dict[str, dict]:
    """Professional-tax rules per state code (``"MH"``, ``"KA"``, …)."""
    return fetch("pt-states", refresh=refresh)["states"]


def pt_free_states(*, refresh: bool = False) -> list[str]:
    """State codes that levy no professional tax at all."""
    return list(fetch("pt-states", refresh=refresh)["none"])


def professional_tax(
    state: str,
    monthly_salary: float,
    *,
    gender: Literal["male", "female"] = "male",
    refresh: bool = False,
) -> float:
    """Monthly professional tax for a salary in a state.

    Returns ``0.0`` for states that do not levy it.

    Maharashtra's February top-up is **not** included — it is an extra amount in
    one month of the year, not a monthly rate. ``pt_states()["MH"]["feb"]`` has it.

    >>> professional_tax("MH", 30000)
    200.0
    >>> professional_tax("DL", 30000)
    0.0
    """
    code = state.strip().upper()
    payload = fetch("pt-states", refresh=refresh)
    if code in payload["none"]:
        return 0.0
    try:
        rules = payload["states"][code]
    except KeyError:
        raise KeyError(
            f"unknown state code {state!r}. Known: {', '.join(sorted(payload['states']))}"
        ) from None

    bands = rules[gender] if rules.get("gender") and gender in rules else rules.get(
        "male", rules.get("bands", [])
    )
    for upper, amount in bands:
        if upper is None or monthly_salary <= upper:
            return float(amount)
    return 0.0


# ──────────────────────────── due dates ────────────────────────────

def due_dates(*, refresh: bool = False) -> dict[str, Any]:
    """Upcoming compliance dates, as published for the site's own calendar."""
    return fetch("due-next", refresh=refresh)


# ──────────────────────────── provenance ────────────────────────────

def verified_on(dataset: str = "rates", *, refresh: bool = False) -> str | None:
    """When this dataset was last checked against its source."""
    payload = fetch(dataset, refresh=refresh)
    if "verified_on" in payload:
        return payload["verified_on"]
    dates = [v.get("verified_on") for v in payload.get("keys", {}).values()]
    dates = [d for d in dates if d]
    return max(dates) if dates else None


def attribution(dataset: str = "rates") -> str:
    """The credit line to print if you publish these figures."""
    payload = fetch(dataset)
    licence = payload.get("_license", "CC BY 4.0 — cite itrsaral.in")
    return f"Data: ITR Saral (https://itrsaral.in/data) — {licence}"
