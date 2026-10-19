"""State public holidays in business-day clocks."""

import json
from datetime import date
from pathlib import Path

import pytest

from src.tools.claims_timeframes import check_claim_timeframe
from src.tools.notifications import (
    STATES,
    add_business_days,
    add_business_days_with_basis,
    assess_regulatory_obligations,
)

DATA = Path(__file__).resolve().parent.parent / "src" / "data" / "holidays" / "au_public_holidays.json"


@pytest.fixture(autouse=True)
def _no_default_state(monkeypatch):
    monkeypatch.delenv("GUARDIAN_STATE", raising=False)


def test_data_file_shape():
    data = json.loads(DATA.read_text())
    assert data["verified_on"] == "2026-10-19"
    assert set(data["holidays"]) == set(STATES)
    for state, years in data["holidays"].items():
        assert set(years) == {"2025", "2026", "2027"}, state
        assert state in data["sources"]
        for year, entries in years.items():
            assert all(e["date"].startswith(year) for e in entries), (state, year)


def test_vic_melbourne_cup_2026_moves_deadline():
    start = date(2026, 10, 26)
    assert add_business_days(start, 10) == date(2026, 11, 9)
    assert add_business_days(start, 10, "VIC") == date(2026, 11, 10)
    assert add_business_days(start, 10, "NSW") == date(2026, 11, 9)


def test_nsw_labour_day_2026():
    start = date(2026, 9, 28)
    assert add_business_days(start, 10, "NSW") == date(2026, 10, 13)
    assert add_business_days(start, 10, "VIC") == date(2026, 10, 12)


def test_qld_labour_day_is_first_monday_of_may_2026_and_kings_birthday_is_october():
    # QLD Labour Day is 4 May 2026 and the King's Birthday is 5 October 2026.
    assert add_business_days(date(2026, 4, 27), 10, "QLD") == date(2026, 5, 12)
    assert add_business_days(date(2026, 4, 27), 10, "NSW") == date(2026, 5, 11)
    assert add_business_days(date(2026, 9, 28), 10, "QLD") == date(2026, 10, 13)


def test_wa_labour_day_in_march_2026():
    start = date(2026, 2, 23)
    assert add_business_days(start, 10, "WA") == date(2026, 3, 10)
    assert add_business_days(start, 10, "NSW") == date(2026, 3, 9)


def test_sa_part_day_christmas_eve_is_not_excluded():
    # 24 December 2026 is a part-day holiday in SA (7pm to midnight), so the whole day still counts.
    assert add_business_days(date(2026, 12, 23), 1, "SA") == date(2026, 12, 24)


def test_state_code_is_case_insensitive_and_basis_reported():
    due, basis = add_business_days_with_basis(date(2026, 10, 26), 10, "vic")
    assert due == date(2026, 11, 10)
    assert basis == "VIC public holidays"


def test_no_state_uses_national_and_says_so():
    due, basis = add_business_days_with_basis(date(2026, 10, 26), 10)
    assert due == date(2026, 11, 9)
    assert basis.startswith("national public holidays only")


def test_missing_year_falls_back_to_national():
    due, basis = add_business_days_with_basis(date(2028, 2, 28), 10, "VIC")
    assert due == add_business_days(date(2028, 2, 28), 10)
    assert "no VIC data for 2028" in basis


def test_span_into_missing_year_reports_fallback_year():
    _, basis = add_business_days_with_basis(date(2027, 12, 29), 10, "NSW")
    assert "no NSW data for 2028" in basis


def test_unknown_state_falls_back_to_national():
    due, basis = add_business_days_with_basis(date(2026, 10, 26), 10, "XX")
    assert due == date(2026, 11, 9)
    assert basis.startswith("national public holidays only")


def test_env_default_state(monkeypatch):
    monkeypatch.setenv("GUARDIAN_STATE", "VIC")
    assert add_business_days(date(2026, 10, 26), 10) == date(2026, 11, 10)
    # An explicit state overrides the environment default.
    assert add_business_days(date(2026, 10, 26), 10, "NSW") == date(2026, 11, 9)


def test_obligations_report_state_basis():
    res = assess_regulatory_obligations(["apra_cps234_36"], detected_at="2026-10-26T09:00:00+00:00", state="VIC")
    ob = res["obligations"][0]
    assert ob["due"] == "2026-11-10"
    assert "VIC public holidays" in ob["day_basis"]

    national = assess_regulatory_obligations(["apra_cps234_36"], detected_at="2026-10-26T09:00:00+00:00")
    assert national["obligations"][0]["due"] == "2026-11-09"
    assert "national public holidays only" in national["obligations"][0]["day_basis"]


def test_claim_timeframe_reports_state_basis():
    res = check_claim_timeframe("general_insurance", "2026-10-01", info_complete_on="2026-10-26",
                                today="2026-10-27", state="VIC")
    decision = next(c for c in res["checks"] if c["check"].startswith("Decision after"))
    assert decision["due"] == "2026-11-10"
    assert "VIC public holidays" in res["day_basis"]
