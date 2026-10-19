"""Claim timeframe checks against the General and Life Insurance Codes of Practice.

Timeframes come from the `timeframes` object stored in each Code's corpus file, so a Code update only needs a data
change. Private health claims are governed by fund rules rather than a Code claims timetable, so they are not checked.
"""

import calendar
from datetime import date
from typing import Any, Dict, Optional

from src.db import get_standard_by_code
from src.tools.notifications import add_business_days_with_basis

_SECTOR_CODE = {"general_insurance": "GI Code", "life_insurance": "Life Code"}


def _parse(d: Optional[str]) -> Optional[date]:
    return date.fromisoformat(d) if d else None


def _add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def code_timeframes(code: str) -> Dict[str, Any]:
    inst = get_standard_by_code(code)
    return (inst or {}).get("extra", {}).get("timeframes", {}) if inst else {}


def check_claim_timeframe(
    sector: str,
    lodged_on: str,
    info_complete_on: Optional[str] = None,
    today: Optional[str] = None,
    product: Optional[str] = None,
    last_update_on: Optional[str] = None,
    state: Optional[str] = None,
) -> Dict[str, Any]:
    code = _SECTOR_CODE.get((sector or "").lower().strip())
    if not code:
        return {"error": "Claim timeframes are checked for 'general_insurance' and 'life_insurance' only. Private health claims follow fund rules."}
    tf = code_timeframes(code)
    if not tf:
        return {"error": f"No timeframes recorded for {code} in the corpus."}

    lodged = _parse(lodged_on)
    as_of = _parse(today) or date.today()
    info_done = _parse(info_complete_on)
    checks = []
    bases: list = []

    def bdays(start: date, days: int) -> date:
        due, basis = add_business_days_with_basis(start, days, state)
        bases.append(basis)
        return due

    def check(name: str, due: date, basis: str, citation: str) -> None:
        status = "overdue" if as_of > due else ("due today" if as_of == due else "within timeframe")
        checks.append({"check": name, "due": due.isoformat(), "status": status, "days_remaining": (due - as_of).days,
                       "basis": basis, "citation": f"{code} {citation}"})

    decision_bd = tf.get("claim_decision_after_info_business_days")
    if info_done and decision_bd:
        check("Decision after all information received", bdays(info_done, decision_bd),
              f"{decision_bd} business days after all necessary information is received", "claim_decision_timeframe")

    if code == "GI Code":
        months = tf.get("claim_overall_decision_months")
        if months:
            check("Overall claim decision limit", _add_months(lodged, months),
                  f"{months} months from lodgement unless exceptional circumstances apply (then up to "
                  f"{tf.get('claim_overall_decision_exception_months', 12)} months with notice and AFCA rights)", "claim_overall_timeframe")
    else:
        per_product = tf.get("claim_decision_months", {})
        key = (product or "").lower().strip().replace(" ", "_").replace("-", "_")
        if key in per_product:
            check(f"Claim decision limit ({key})", _add_months(lodged, per_product[key]),
                  f"{per_product[key]} months from the {tf.get('claim_decision_clock_start', 'claim received date')}", "claim_decision_timeframe")
        elif product:
            checks.append({"check": "Claim decision limit", "status": "unknown product",
                           "basis": f"Known products: {', '.join(sorted(per_product))}"})

    update_bd = tf.get("claim_update_interval_business_days")
    if update_bd:
        anchor = _parse(last_update_on) or lodged
        check("Next customer update", bdays(anchor, update_bd),
              f"Update at least every {update_bd} business days", "claim_updates")

    overdue = [c for c in checks if c.get("status") == "overdue"]
    return {
        "code": code,
        "sector": sector,
        "as_of": as_of.isoformat(),
        "checks": checks,
        "day_basis": f"business days ({bases[-1] if bases else add_business_days_with_basis(lodged, 0, state)[1]} excluded)",
        "overdue_count": len(overdue),
        "advisory": (
            "An overdue Code timeframe is a potential Code breach to record and assess for significance. Business days "
            "exclude the public holidays named in day_basis; confirm local holidays and any Code exceptions."
        ),
    }
