"""Tests run against fixtures, not the network.

A test suite that needs the internet is a test suite that fails on a train.
The fixtures below are trimmed copies of the real payloads.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import itrsaral  # noqa: E402
from itrsaral import _client  # noqa: E402

RATES = {
    "_license": "CC BY 4.0 — cite itrsaral.in",
    "keys": {
        "ppf": {"value": 7.1, "unit": "%", "group": "savings", "en": "PPF interest rate",
                "source": "https://dea.gov.in/budget-division/475", "verified_on": "2026-10-01"},
        "epf": {"value": 8.25, "unit": "%", "group": "savings", "en": "EPF interest rate",
                "source": "https://www.epfindia.gov.in/", "verified_on": "2026-09-28"},
        "std_new": {"value": 75000, "unit": "INR", "group": "income-tax",
                    "en": "Standard deduction (new regime)", "verified_on": "2026-09-19"},
    },
}

SLABS = {
    "newRegime": {"ty2627": {"slabs": [[400000, 0], [800000, 0.05], [None, 0.3]]}},
    "oldRegime": {"slabs": [[250000, 0], [500000, 0.05], [None, 0.3]],
                  "exempt": {"below60": 250000, "60to80": 300000, "above80": 500000}},
    "surcharge": [[50000000, 0.37, 0.25], [10000000, 0.15, 0.15]],
    "verified_on": "2026-09-19",
}

PT = {
    "none": ["DL", "UP"],
    "states": {
        "MH": {"name": "Maharashtra", "basis": "monthly", "gender": True,
               "male": [[7500, 0], [10000, 175], [None, 200]],
               "female": [[25000, 0], [None, 200]], "feb": 300},
        "KA": {"name": "Karnataka", "basis": "monthly",
               "male": [[24999, 0], [None, 200]]},
    },
    "verified_on": "2026-09-18",
}

FIXTURES = {"rates": RATES, "slabs": SLABS, "pt-states": PT,
            "due-next": {"built": "2026-10-25", "topics": []}}


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    """Every test runs against fixtures, with caches isolated per test."""
    monkeypatch.setattr(_client, "CACHE_DIR", str(tmp_path))
    _client._memory.clear()
    monkeypatch.setattr(_client, "fetch",
                        lambda name, **kw: json.loads(json.dumps(FIXTURES[name])))
    monkeypatch.setattr(itrsaral, "fetch",
                        lambda name, **kw: json.loads(json.dumps(FIXTURES[name])))


# ───────────────────────────── rates ─────────────────────────────

def test_rate_returns_the_number():
    assert itrsaral.rate("ppf") == 7.1


def test_rate_info_carries_its_source():
    assert itrsaral.rate_info("ppf")["source"].startswith("https://")


def test_unknown_rate_suggests_near_misses():
    with pytest.raises(KeyError, match="std_new"):
        itrsaral.rate("std")


def test_rates_filter_by_group():
    assert set(itrsaral.rates(group="savings")) == {"ppf", "epf"}


def test_groups_are_sorted_and_unique():
    assert itrsaral.groups() == ["income-tax", "savings"]


# ───────────────────────────── slabs ─────────────────────────────

def test_new_regime_first_band_is_nil():
    assert itrsaral.tax_slabs("new", "ty2627")[0] == (400000, 0.0)


def test_last_band_is_open_ended():
    assert itrsaral.tax_slabs("new", "ty2627")[-1] == (None, 0.3)


def test_old_regime_differs_from_new():
    assert itrsaral.tax_slabs("old")[0] != itrsaral.tax_slabs("new")[0]


def test_unknown_year_names_what_exists():
    with pytest.raises(KeyError, match="ty2627"):
        itrsaral.tax_slabs("new", "fy9999")  # type: ignore[arg-type]


def test_old_regime_ignores_year_because_upstream_has_one_set():
    # असली data में oldRegime साल-वार नहीं है — year देने पर भी वही बैंड आने चाहिए
    assert itrsaral.tax_slabs("old", "ty2627") == itrsaral.tax_slabs("old", "fy2526")


def test_senior_exemption_rises_with_age():
    assert itrsaral.exempt_limit("below60") < itrsaral.exempt_limit("60to80")
    assert itrsaral.exempt_limit("60to80") < itrsaral.exempt_limit("above80")


def test_unknown_age_band_lists_the_valid_ones():
    with pytest.raises(KeyError, match="below60"):
        itrsaral.exempt_limit("teen")  # type: ignore[arg-type]


def test_surcharge_is_richest_first():
    bands = itrsaral.surcharge()
    assert bands[0][0] > bands[-1][0]


# ─────────────────────── professional tax ───────────────────────

def test_pt_zero_below_the_first_band():
    assert itrsaral.professional_tax("MH", 7000) == 0.0


def test_pt_middle_band():
    assert itrsaral.professional_tax("MH", 9000) == 175.0


def test_pt_top_band_is_open_ended():
    assert itrsaral.professional_tax("MH", 500000) == 200.0


def test_pt_women_get_the_higher_threshold():
    # ₹20,000 is taxable for a man in Maharashtra, exempt for a woman
    assert itrsaral.professional_tax("MH", 20000, gender="male") == 200.0
    assert itrsaral.professional_tax("MH", 20000, gender="female") == 0.0


def test_pt_free_state_is_zero_not_an_error():
    assert itrsaral.professional_tax("DL", 100000) == 0.0


def test_pt_state_code_is_case_insensitive():
    assert itrsaral.professional_tax("mh", 9000) == 175.0


def test_pt_unknown_state_lists_the_known_ones():
    with pytest.raises(KeyError, match="MH"):
        itrsaral.professional_tax("ZZ", 10000)


def test_february_topup_is_not_folded_into_the_monthly_figure():
    # Maharashtra's extra ₹300 lands in one month; the monthly rate must stay 200
    assert itrsaral.professional_tax("MH", 500000) == 200.0
    assert itrsaral.pt_states()["MH"]["feb"] == 300


# ─────────────────────────── provenance ───────────────────────────

def test_verified_on_reads_the_dataset_field():
    assert itrsaral.verified_on("slabs") == "2026-09-19"


def test_verified_on_rates_takes_the_newest_key():
    assert itrsaral.verified_on("rates") == "2026-10-01"


def test_attribution_names_the_site():
    assert "itrsaral.in" in itrsaral.attribution()
