"""Statutory notification advisor and decision tree for APRA incidents."""

from typing import Any, Dict, List
from src.db import get_all_notifications


def assess_notification_requirements(
    incident_type: str,
    is_cyber_or_infosec: bool = False,
    exceeds_tolerance: bool = False,
    is_material_impact: bool = True,
    notified_to_other_regulators: bool = False,
    is_control_weakness: bool = False
) -> Dict[str, Any]:
    """
    Evaluates an operational incident or control finding against APRA statutory notification mandates.
    Applies the specific rules from CPS 230 (paras 33, 42) and CPS 234 (paras 35, 36).
    """
    applicable_obligations: List[Dict[str, Any]] = []
    warnings: List[str] = []

    # 1. 24-HOUR NOTIFICATION: Disruption outside tolerance (CPS 230 para 42)
    if exceeds_tolerance:
        applicable_obligations.append({
            "standard": "CPS 230",
            "clause": "Paragraph 42",
            "timeframe": "24 hours",
            "urgency": "CRITICAL",
            "trigger": "Disruption to a critical operation outside Board-approved tolerance levels (outage duration, data loss, or minimum service level).",
            "mandatory_reporting_content": [
                "Nature of disruption",
                "Immediate actions taken",
                "Likely impact on depositors/policyholders/customers",
                "Estimated timeframe for returning to normal operations"
            ]
        })
        warnings.append("CRITICAL: Disruption outside tolerance triggers APRA's strictest 24-hour notification deadline.")

    # 2. 72-HOUR NOTIFICATION: Cyber / Information Security Incident (CPS 234 para 35)
    if is_cyber_or_infosec and (is_material_impact or notified_to_other_regulators):
        applicable_obligations.append({
            "standard": "CPS 234",
            "clause": "Paragraph 35",
            "timeframe": "72 hours",
            "urgency": "HIGH",
            "trigger": "Material information security incident (affecting confidentiality, integrity, availability) OR incident notified to other regulators (e.g. OAIC under Notifiable Data Breaches, ASIC, ACSC).",
            "mandatory_reporting_content": [
                "Description of cyber/security incident and affected assets",
                "Impact on customer data, confidentiality, integrity, availability",
                "Containment actions and status of investigations",
                "Details of other regulators notified (OAIC, ACSC, etc.)"
            ]
        })

    # 3. 72-HOUR NOTIFICATION: General Operational Risk Incident (CPS 230 para 33)
    if not is_cyber_or_infosec and is_material_impact and not exceeds_tolerance:
        applicable_obligations.append({
            "standard": "CPS 230",
            "clause": "Paragraph 33",
            "timeframe": "72 hours",
            "urgency": "HIGH",
            "trigger": "Operational risk incident determined likely to have a material financial impact or material impact on maintaining critical operations.",
            "mandatory_reporting_content": [
                "Description of operational failure and root cause",
                "Financial impact assessment",
                "Impact on critical operations",
                "Remediation roadmap"
            ]
        })

    # 4. DE-DUPLICATION RULE (CPS 230 Footnote 11)
    deduplication_applied = False
    if is_cyber_or_infosec and is_material_impact:
        deduplication_applied = True
        warnings.append(
            "DE-DUPLICATION RULE APPLIED (CPS 230 Footnote 11): Because this is an information security incident "
            "reported under CPS 234 (para 35), you are EXEMPT from submitting a duplicate operational risk incident report "
            "under CPS 230 (para 33). However, if the disruption also exceeds approved tolerance levels, the separate 24-hour "
            "notification under CPS 230 (para 42) remains mandatory."
        )

    # 5. 10-BUSINESS-DAY NOTIFICATION: Control Weakness (CPS 234 para 36)
    if is_control_weakness:
        applicable_obligations.append({
            "standard": "CPS 234",
            "clause": "Paragraph 36",
            "timeframe": "10 business days",
            "urgency": "MEDIUM",
            "trigger": "Material information security control weakness identified that cannot be remediated in a timely manner.",
            "mandatory_reporting_content": [
                "Description of control vulnerability",
                "Impacted systems and information assets",
                "Reasons timely remediation is unachievable",
                "Compensating controls and revised remediation plan"
            ]
        })

    if not applicable_obligations:
        applicable_obligations.append({
            "standard": "None triggered",
            "clause": "N/A",
            "timeframe": "No immediate statutory reporting triggered",
            "urgency": "ROUTINE",
            "trigger": "Incident appears to be within internal risk appetite and tolerance levels without material customer or financial impact.",
            "mandatory_reporting_content": [
                "Log in internal incident register and track near misses per CPS 230 para 32."
            ]
        })

    return {
        "incident_assessment": {
            "incident_type": incident_type,
            "is_cyber": is_cyber_or_infosec,
            "tolerance_exceeded": exceeds_tolerance,
            "material_impact": is_material_impact
        },
        "applicable_statutory_obligations": applicable_obligations,
        "deduplication_rule_active": deduplication_applied,
        "advisory_notes": warnings
    }


def list_all_notification_rules() -> List[Dict[str, Any]]:
    """Returns the comprehensive table of all APRA notification triggers across CPS 230 and CPS 234."""
    return get_all_notifications()


# ============================================================================
# Multi-regulator obligation clocks (APRA, ASIC, OAIC, Code bodies, ACSC)
# ============================================================================

import json
import os
from datetime import date, datetime, time as dtime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional, Tuple, Union

INSURANCE_SECTORS = ("general_insurance", "life_insurance", "private_health_insurance")
AFSL_SECTORS = ("general_insurance", "life_insurance")

# Each clock: who, under what, how long, and on what day basis. "conditional" clocks only start once the
# entity concludes the condition is met (for example that a breach is significant); the deadline is then
# measured from detection as the latest defensible date.
OBLIGATION_CLOCKS: Dict[str, Dict[str, Any]] = {
    "apra_cps230_42": {
        "regulator": "APRA", "instrument": "CPS 230", "clause": "42", "hours": 24,
        "obligation": "Notify APRA of a disruption to a critical operation outside tolerance.",
        "conditional": False,
    },
    "apra_cps230_33": {
        "regulator": "APRA", "instrument": "CPS 230", "clause": "33", "hours": 72,
        "obligation": "Notify APRA of an operational risk incident likely to have a material financial impact or a material impact on critical operations.",
        "conditional": True, "condition": "Measured from when the entity determines the incident is material.",
    },
    "apra_cps234_35": {
        "regulator": "APRA", "instrument": "CPS 234", "clause": "35", "hours": 72,
        "obligation": "Notify APRA of a material information security incident, or one notified to another regulator.",
        "conditional": False,
    },
    "apra_cps234_36": {
        "regulator": "APRA", "instrument": "CPS 234", "clause": "36", "business_days": 10,
        "obligation": "Notify APRA of a material information security control weakness that cannot be remediated in a timely manner.",
        "conditional": True, "condition": "Measured from when the entity becomes aware of the weakness.",
    },
    "asic_reportable_situation": {
        "regulator": "ASIC", "instrument": "Corporations Act 2001", "clause": "912DAA", "calendar_days": 30,
        "obligation": "Lodge a breach report with ASIC for a reportable situation (for example a significant breach of a core obligation such as s912A or a civil penalty provision).",
        "conditional": True,
        "condition": "Applies once the licensee knows, or is reckless as to whether, there are reasonable grounds to believe a reportable situation has arisen. An investigation running more than 60 days is itself reportable (s912D(1)(c) says 30 days; ASIC Instrument 2024/620 extends it to 60 from 24 June 2025). A report to APRA by an APRA-regulated licensee can count as lodged with ASIC (s912DAA(5)).",
        "sectors": AFSL_SECTORS,
        "guidance": "RG 78",
    },
    "oaic_ndb": {
        "regulator": "OAIC", "instrument": "Privacy Act 1988", "clause": "26WH", "calendar_days": 30,
        "obligation": "Complete a reasonable and expeditious assessment of a suspected eligible data breach; if eligible, notify the OAIC and affected individuals as soon as practicable (s26WK, s26WL).",
        "conditional": False,
    },
    "code_breach_report": {
        "regulator": "Code compliance committee", "instrument": "GI Code / Life Code / PHI Code", "clause": "code_breach_reporting",
        "business_days": 10,
        "obligation": "Report significant Code breaches to the relevant Code compliance committee within the Code's timeframe.",
        "conditional": True, "condition": "Applies to breaches the subscriber assesses as significant; check the current Code text for the exact timeframe.",
        "sectors": INSURANCE_SECTORS,
    },
    "idr_complaint": {
        "regulator": "ASIC (IDR) / AFCA", "instrument": "RG 271", "clause": "idr_response_timeframe", "calendar_days": 30,
        "acknowledge_business_days": 1,
        "obligation": "Acknowledge the complaint within 24 hours or one business day, and give an IDR response within 30 calendar days with AFCA details if not fully resolved.",
        "conditional": False,
        "sectors": AFSL_SECTORS,
    },
    "ddo_significant_dealing": {
        "regulator": "ASIC", "instrument": "Corporations Act 2001", "clause": "994G", "business_days": 10,
        "obligation": "Notify ASIC (issuer) of a significant dealing inconsistent with the TMD; distributors must tell the issuer as soon as practicable and within 10 business days.",
        "conditional": True, "condition": "Applies if the dealing is significant (consider scale, harm and pattern).",
        "sectors": AFSL_SECTORS,
    },
    "soci_critical_cyber": {
        "regulator": "ASD ACSC", "instrument": "SOCI Act 2018", "clause": "30BC", "hours": 12,
        "obligation": "Report a critical cyber security incident with significant impact on a critical infrastructure asset.",
        "conditional": True, "condition": "Only for responsible entities of a critical insurance asset.",
        "requires_profile": "soci_critical_insurance_asset",
    },
    "soci_other_cyber": {
        "regulator": "ASD ACSC", "instrument": "SOCI Act 2018", "clause": "30BD", "hours": 72,
        "obligation": "Report a cyber security incident with relevant impact on a critical infrastructure asset.",
        "conditional": True, "condition": "Only for responsible entities of a critical insurance asset.",
        "requires_profile": "soci_critical_insurance_asset",
    },
    "far_notification": {
        "regulator": "APRA and ASIC", "instrument": "FAR Act 2023", "clause": "notification_obligations", "calendar_days": 30,
        "obligation": "Notify the Regulator of FAR notifiable events and material changes (for example accountable person changes, or a breach of accountability obligations).",
        "conditional": True, "condition": "Applies to accountable entities (insurers from 15 March 2025) unless the Regulator rules prescribe another period.",
    },
    "ransomware_payment": {
        "regulator": "ASD / Home Affairs", "instrument": "Cyber Security Act 2024", "clause": "ransomware_payment_report", "hours": 72,
        "obligation": "Report a ransomware or cyber extortion payment within 72 hours of making it (entities above the turnover threshold).",
        "conditional": False,
    },
}

_CODE_FOR_SECTOR = {"general_insurance": "GI Code", "life_insurance": "Life Code", "private_health_insurance": "PHI Code"}


def _code_breach_days(code: str) -> Optional[int]:
    from src.db import get_standard_by_code

    inst = get_standard_by_code(code)
    if not inst:
        return None
    tf = inst.get("extra", {}).get("timeframes", {})
    return tf.get("significant_breach_report_business_days")


# PII incidents are cyber incidents for SOCI purposes when the profile says the entity runs a critical asset.
_TRIGGER_IMPLIES = {"apra_cps234_35": ("soci_other_cyber",)}


def _easter_sunday(year: int) -> date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _observed(d: date) -> date:
    if d.weekday() == 5:
        return d + timedelta(days=2)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


@lru_cache(maxsize=16)
def national_public_holidays(year: int) -> frozenset:
    """Holidays observed in every state and territory. State-only days (King's Birthday, Labour Day) are excluded."""
    easter = _easter_sunday(year)
    christmas = date(year, 12, 25)
    boxing = date(year, 12, 26)
    days = {
        _observed(date(year, 1, 1)),
        _observed(date(year, 1, 26)),
        easter - timedelta(days=2),
        easter + timedelta(days=1),
        date(year, 4, 25),
    }
    if christmas.weekday() == 5:
        days |= {date(year, 12, 27), date(year, 12, 28)}
    elif christmas.weekday() == 6:
        days |= {date(year, 12, 26), date(year, 12, 27)}
    elif boxing.weekday() == 5:
        days |= {christmas, date(year, 12, 28)}
    else:
        days |= {christmas, boxing}
    return frozenset(days)


_HOLIDAY_FILE = Path(__file__).resolve().parent.parent / "data" / "holidays" / "au_public_holidays.json"
STATES = ("ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA")


@lru_cache(maxsize=1)
def _state_holiday_data() -> Dict[str, Dict[str, frozenset]]:
    """{state: {year: frozenset of dates}} from the verified data file (whole-day statewide holidays only)."""
    raw = json.loads(_HOLIDAY_FILE.read_text(encoding="utf-8"))["holidays"]
    return {st: {yr: frozenset(date.fromisoformat(e["date"]) for e in entries) for yr, entries in years.items()}
            for st, years in raw.items()}


def resolve_state(state: Optional[str] = None) -> Optional[str]:
    """An explicit state wins, then GUARDIAN_STATE; None when neither is set or the value is not a state code."""
    value = (state or os.environ.get("GUARDIAN_STATE") or "").strip().upper()
    return value if value in STATES else None


def add_business_days_with_basis(start: date, days: int, state: Optional[str] = None) -> Tuple[date, str]:
    """Add business days and report which holiday list was used.

    A state's holidays come from the data file; any year the file lacks falls back to the computed national set.
    """
    st = resolve_state(state)
    by_year = _state_holiday_data().get(st, {}) if st else {}
    fallback_years = set()

    def is_holiday(d: date) -> bool:
        if str(d.year) in by_year:
            return d in by_year[str(d.year)]
        fallback_years.add(d.year)
        return d in national_public_holidays(d.year)

    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5 and not is_holiday(current):
            added += 1

    if not st:
        basis = "national public holidays only; pass state or set GUARDIAN_STATE for state holidays"
    elif not fallback_years:
        basis = f"{st} public holidays"
    else:
        years = ", ".join(str(y) for y in sorted(fallback_years))
        basis = f"national public holidays only (no {st} data for {years})"
    return current, basis


def add_business_days(start: date, days: int, state: Optional[str] = None) -> date:
    return add_business_days_with_basis(start, days, state)[0]


def _parse_when(detected_at: Optional[Union[str, datetime, date]]) -> datetime:
    if detected_at is None:
        return datetime.now(timezone.utc)
    if isinstance(detected_at, datetime):
        return detected_at if detected_at.tzinfo else detected_at.replace(tzinfo=timezone.utc)
    if isinstance(detected_at, date):
        return datetime.combine(detected_at, dtime(9, 0), tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(detected_at).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _deadline(clock: Dict[str, Any], start: datetime, state: Optional[str] = None) -> Dict[str, Any]:
    if "hours" in clock:
        due = start + timedelta(hours=clock["hours"])
        return {"timeframe": f"{clock['hours']} hours", "due": due.isoformat(timespec="minutes"), "day_basis": "clock hours"}
    if "business_days" in clock:
        due, basis = add_business_days_with_basis(start.date(), clock["business_days"], state)
        return {"timeframe": f"{clock['business_days']} business days", "due": due.isoformat(), "day_basis": f"business days ({basis} excluded)"}
    due = start.date() + timedelta(days=clock["calendar_days"])
    return {"timeframe": f"{clock['calendar_days']} calendar days", "due": due.isoformat(), "day_basis": "calendar days"}


def assess_regulatory_obligations(
    triggers: Iterable[str],
    sectors: Optional[Iterable[str]] = None,
    detected_at: Optional[Union[str, datetime, date]] = None,
    entity_profile: Optional[Dict[str, Any]] = None,
    state: Optional[str] = None,
) -> Dict[str, Any]:
    """Turn breach triggers into dated, per-regulator obligations.

    Args:
        triggers: Clock keys from OBLIGATION_CLOCKS (rules emit these).
        sectors: Sectors the entity operates in; clocks limited to other sectors are reported as not applicable.
        detected_at: When the issue was detected (ISO string or datetime, defaults to now, UTC).
        entity_profile: Optional facts, e.g. {"soci_critical_insurance_asset": True}.
        state: State or territory code (e.g. VIC) for state public holidays in business-day clocks; defaults to GUARDIAN_STATE.
    """
    profile = entity_profile or {}
    sector_set = set(sectors or INSURANCE_SECTORS)
    start = _parse_when(detected_at)

    expanded: List[str] = []
    for t in triggers:
        for key in (t, *_TRIGGER_IMPLIES.get(t, ())):
            if key not in expanded:
                expanded.append(key)

    obligations, not_applicable = [], []
    for key in expanded:
        clock = OBLIGATION_CLOCKS.get(key)
        if not clock:
            continue
        if key == "code_breach_report":
            # Each Code sets its own significant-breach reporting window; read it from the corpus.
            for sector_name, code_name in _CODE_FOR_SECTOR.items():
                if sector_name not in sector_set:
                    continue
                days = _code_breach_days(code_name)
                sector_clock = {**clock, "instrument": code_name}
                if days:
                    sector_clock["business_days"] = days
                else:
                    sector_clock.pop("business_days", None)
                    sector_clock["calendar_days"] = 30
                    sector_clock["condition"] = clock["condition"] + " Timeframe not recorded in the corpus; 30 days shown as a placeholder."
                entry = {
                    "trigger": key, "regulator": clock["regulator"], "instrument": code_name,
                    "clause": "code_breach_reporting", "obligation": clock["obligation"], "status": "conditional",
                    **_deadline(sector_clock, start, state), "condition": sector_clock["condition"],
                }
                obligations.append(entry)
            continue
        reason = None
        if clock.get("sectors") and not sector_set & set(clock["sectors"]):
            reason = f"Only applies to {', '.join(clock['sectors'])}."
        elif clock.get("requires_profile") and not profile.get(clock["requires_profile"]):
            reason = f"Only applies if entity_profile.{clock['requires_profile']} is true."
        entry = {
            "trigger": key,
            "regulator": clock["regulator"],
            "instrument": clock["instrument"],
            "clause": clock["clause"],
            "obligation": clock["obligation"],
            "status": "conditional" if clock.get("conditional") else "mandatory",
            **_deadline(clock, start, state),
        }
        if clock.get("condition"):
            entry["condition"] = clock["condition"]
        if clock.get("acknowledge_business_days"):
            entry["acknowledge_by"] = add_business_days(start.date(), clock["acknowledge_business_days"], state).isoformat()
        if reason:
            not_applicable.append({**entry, "reason": reason})
        else:
            obligations.append(entry)

    obligations.sort(key=lambda o: o["due"])
    return {
        "detected_at": start.isoformat(timespec="minutes"),
        "obligations": obligations,
        "not_applicable": not_applicable,
        "advisory": (
            "Deadlines are computed from the detection time as the latest defensible date. Conditional clocks start "
            "when the entity forms the relevant view, which may be earlier. This is triage support, not legal advice."
        ),
    }
