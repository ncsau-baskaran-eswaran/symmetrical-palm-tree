"""Coverage map, obligation discovery and customer-message triage built on the registry and the rule catalogue."""

import re
from typing import Any, Dict, List, Optional

from src.db import get_clauses_for, get_clause_by_number, list_instrument_rows, resolve_instrument_code
from src.rules.audit import describe_obligation, resolve_sectors
from src.rules.catalog import JUDGE_ONLY_CATEGORIES, RULES
from src.tools.notifications import assess_regulatory_obligations

# Controls the white-box code auditor verifies (src/code_auditor/analyzer.py).
CODE_INSPECTED = {("CPS 234", "21"), ("CPS 234", "23"), ("CPS 230", "29"), ("CPS 230", "36")}

STATUS_ORDER = (
    "runtime_detected",
    "review_flag",
    "judge_only",
    "code_inspection",
    "governance_checklist",
    "reference_only",
    "out_of_scope_not_agent_testable",
)


def _clause_key(code: str, clause: str) -> Optional[tuple]:
    resolved = resolve_instrument_code(code)
    if not resolved:
        return None
    cl = get_clause_by_number(resolved, clause)
    return (resolved, cl["clause_number"]) if cl else None


def _rule_index() -> Dict[tuple, Dict[str, Any]]:
    index: Dict[tuple, Dict[str, Any]] = {}

    def add(key: Optional[tuple], status: str, category: str) -> None:
        if not key:
            return
        entry = index.setdefault(key, {"status": status, "categories": []})
        if STATUS_ORDER.index(status) < STATUS_ORDER.index(entry["status"]):
            entry["status"] = status
        if category not in entry["categories"]:
            entry["categories"].append(category)

    for rule in RULES:
        for ref in rule.obligations:
            add(_clause_key(ref.code, ref.clause), "review_flag" if rule.review_only else "runtime_detected", rule.category)
    for category, (_desc, refs) in JUDGE_ONLY_CATEGORIES.items():
        for ref in refs:
            add(_clause_key(ref.code, ref.clause), "judge_only", category)
    return index


def _clause_status(code: str, clause: Dict[str, Any], default: str, index: Dict[tuple, Dict[str, Any]]) -> Dict[str, Any]:
    key = (code, clause["clause_number"])
    if key in index:
        return index[key]
    if key in CODE_INSPECTED:
        return {"status": "code_inspection", "categories": []}
    relevance = clause.get("agent_relevance")
    if relevance == "governance":
        return {"status": "governance_checklist", "categories": []}
    if relevance == "none":
        return {"status": "out_of_scope_not_agent_testable", "categories": []}
    if relevance == "code":
        return {"status": "code_inspection", "categories": []}
    return {"status": default if default in STATUS_ORDER else "reference_only", "categories": []}


def get_coverage_map(sector: Optional[str] = None, include_clauses: bool = False, sectors: Optional[set] = None) -> Dict[str, Any]:
    """Honest-scope map: for every instrument and clause, how (or whether) the MCP tests it."""
    index = _rule_index()
    wanted = {sector} if sector else (set(sectors) if sectors else None)
    instruments = []
    totals: Dict[str, int] = {s: 0 for s in STATUS_ORDER}
    runtime_gaps = []
    for inst in list_instrument_rows():
        if wanted and not wanted & set(inst["sectors"]):
            continue
        counts: Dict[str, int] = {s: 0 for s in STATUS_ORDER}
        clauses_out = []
        for clause in get_clauses_for(inst["code"]):
            st = _clause_status(inst["code"], clause, inst["coverage_default"], index)
            counts[st["status"]] += 1
            totals[st["status"]] += 1
            if clause.get("agent_relevance") == "runtime" and st["status"] in ("reference_only", "governance_checklist"):
                runtime_gaps.append(f"{inst['code']} {clause['clause_number']}: {clause['heading']}")
            if include_clauses:
                clauses_out.append({"clause": clause["clause_number"], "heading": clause["heading"], **st})
        entry = {
            "code": inst["code"],
            "regulator": inst["regulator"],
            "status": inst["status"],
            "enforceability": inst["enforceability"],
            "clauses": inst["clause_count"],
            "coverage": {k: v for k, v in counts.items() if v},
            "instrument_default": inst["coverage_default"],
            "verified_on": inst["verified_on"] or "not yet verified",
        }
        if include_clauses:
            entry["clause_detail"] = clauses_out
        instruments.append(entry)
    return {
        "sector_filter": sector or (sorted(wanted) if wanted else "all"),
        "instruments": instruments,
        "totals": {k: v for k, v in totals.items() if v},
        "runtime_relevant_but_not_detected": runtime_gaps,
        "status_meaning": {
            "runtime_detected": "A deterministic rule flags breaches of this clause in agent transcripts.",
            "review_flag": "A rule raises a human-review flag (omissions cannot be proven from one turn).",
            "judge_only": "Only the optional semantic judge can raise it, as a review flag.",
            "code_inspection": "Verified by the white-box code auditor (analyze_agent_code).",
            "governance_checklist": "A governance or documentation obligation; not testable from agent behaviour.",
            "reference_only": "Searchable and citable, not tested.",
            "out_of_scope_not_agent_testable": "Capital, valuation or reporting obligations unrelated to agent conduct.",
        },
    }


def get_obligations_for_agent(agent_role: str, sector: Optional[str] = None) -> Dict[str, Any]:
    """What this agent can breach: applicable rules, the obligations they test, and runtime-relevant clauses left to review."""
    sectors = resolve_sectors(agent_role, sector)
    rules = [r for r in RULES if r.sectors & sectors]
    tested = []
    seen = set()
    for r in rules:
        if r.category in seen:
            continue
        seen.add(r.category)
        tested.append({
            "category": r.category,
            "family": r.family,
            "detection": "review_flag" if r.review_only else "rule",
            "what_it_catches": r.finding,
            "obligations": [describe_obligation(o) for o in r.obligations if o.sectors & sectors],
        })
    index = _rule_index()
    untested = []
    for inst in list_instrument_rows():
        if not sectors & set(inst["sectors"]):
            continue
        for clause in get_clauses_for(inst["code"]):
            if clause.get("agent_relevance") != "runtime" or not sectors & set(clause.get("sectors") or inst["sectors"]):
                continue
            if (inst["code"], clause["clause_number"]) not in index:
                untested.append({"instrument": inst["code"], "clause": clause["clause_number"], "heading": clause["heading"]})
    return {
        "agent_role": agent_role,
        "sectors": sorted(sectors),
        "tested_categories": tested,
        "runtime_obligations_needing_human_review": untested,
    }


def map_finding_to_obligations(category: str, sector: Optional[str] = None) -> Dict[str, Any]:
    sectors = resolve_sectors("", sector) if sector else None
    cat = category.strip().upper()
    rules = [r for r in RULES if r.category == cat]
    if rules:
        obligations, triggers = [], []
        for r in rules:
            for o in r.obligations:
                if sectors and not o.sectors & sectors:
                    continue
                d = describe_obligation(o)
                if d not in obligations:
                    obligations.append(d)
            for t in r.triggers + r.material_triggers:
                if t not in triggers:
                    triggers.append(t)
        return {"category": cat, "finding": rules[0].finding, "obligations": obligations, "reporting_triggers": triggers,
                "remediation": rules[0].remediation}
    if cat in JUDGE_ONLY_CATEGORIES:
        desc, refs = JUDGE_ONLY_CATEGORIES[cat]
        return {"category": cat, "finding": desc, "obligations": [describe_obligation(o) for o in refs], "reporting_triggers": []}
    known = sorted({r.category for r in RULES} | set(JUDGE_ONLY_CATEGORIES))
    return {"error": f"Unknown category '{category}'.", "known_categories": known}


_COMPLAINT = [g for r in RULES if r.id == "CMP-01" for g in r.prompt_gate]
_DISSATISFACTION = [g for r in RULES if r.id == "CMP-02" for g in r.prompt_gate]
_VULNERABILITY = [g for r in RULES if r.id == "VUL-01" for g in r.prompt_gate]
_HARDSHIP = (r"financial hardship", r"can't afford", r"cannot afford", r"struggling to (pay|afford)", r"lost my job", r"made redundant", r"behind on (my )?premiums?")
_FAMILY_VIOLENCE = (r"family violence", r"domestic violence", r"abusive (ex-?partner|partner|ex|husband|wife)", r"my (ex-?partner|partner|ex|husband|wife|boyfriend|girlfriend) (hit|hits|hurt|hurts|threaten|threatens|threatened|controls|abuses|abused|assaulted|stalks)")
_CLAIM_INTENT = (r"\b(lodge|make|submit|file|start) (a |my )?claim\b", r"\bclaim (for|on)\b")


def triage_customer_message(message: str, sector: Optional[str] = None, received_at: Optional[str] = None) -> Dict[str, Any]:
    """Classify a customer message for IDR, vulnerability and hardship duties, with the clocks that start."""
    text = (message or "").lower()

    def hits(patterns) -> List[str]:
        return [m.group(0) for p in patterns for m in [re.search(p, text)] if m]

    complaint, dissatisfied = hits(_COMPLAINT), hits(_DISSATISFACTION)
    vulnerable, hardship, fv, claim = hits(_VULNERABILITY), hits(_HARDSHIP), hits(_FAMILY_VIOLENCE), hits(_CLAIM_INTENT)
    actions, triggers = [], []
    if complaint or dissatisfied:
        triggers.append("idr_complaint")
        actions.append("Treat as a complaint under RG 271: acknowledge it, record it in the IDR register, give a reference, the response timeframe and AFCA details.")
    if fv:
        actions.append("Route to the family violence specialist team; do not contact or disclose to the other party; confirm safe contact methods.")
    if hardship:
        actions.append("Offer financial hardship support under the applicable Code (payment arrangements, premium relief, cash settlement options).")
    if vulnerable and not (fv or hardship):
        actions.append("Flag vulnerability and offer extra care, interpreter or specialist support as the Code requires.")
    if claim:
        actions.append("Lodge or progress the claim; never discourage lodgement.")
    clocks = assess_regulatory_obligations(triggers, sectors=[sector] if sector else None, detected_at=received_at) if triggers else None
    return {
        "is_complaint": bool(complaint),
        "expresses_dissatisfaction": bool(dissatisfied),
        "vulnerability_signals": vulnerable,
        "financial_hardship_signals": hardship,
        "family_violence_signals": fv,
        "claim_intent": bool(claim),
        "required_actions": actions or ["No IDR, hardship or vulnerability duty detected; handle as a standard enquiry."],
        "clocks": clocks,
        "basis": "keyword screen; a human should confirm borderline cases",
    }
