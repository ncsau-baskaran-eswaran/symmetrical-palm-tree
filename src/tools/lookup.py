"""Lookup tools for regulatory instruments (APRA, ASIC, OAIC, Codes, health law) and their clauses."""

import json
from datetime import date
from typing import Any, Dict, List, Optional
from src.db import get_standard_by_code, get_clause_by_number, list_instrument_rows, load_domains, resolve_domain

DISCLAIMER = (
    "Obligations are paraphrased summaries for research, screening and triage, not legal advice. "
    "Always confirm against the source instrument."
)
CURRENT_STATUS = "not established: verified_on is when the source was last checked, not proof it is still current"


def evidence(std: Dict[str, Any], clause: Dict[str, Any]) -> Dict[str, Any]:
    """Citation for one clause: where it comes from, which version, when it was checked, and what kind of text it is.

    `std` uses standards column names (source_url, verified_on, text_kind, legislative_instrument, extra).
    """
    extra = std.get("extra") or {}
    if isinstance(extra, str):
        extra = json.loads(extra)
    text_kind = std.get("text_kind") or "paraphrase"
    source_url = clause.get("source_url") or std.get("source_url")
    out = {
        "source_url": source_url,
        "pinpoint": f"{clause.get('standard_code')} {clause.get('clause_number')}",
        "version": extra.get("source_version") or std.get("legislative_instrument") or None,
        "verified_on": std.get("verified_on") or None,
        "current_status": CURRENT_STATUS,
        "expert_reviewed": bool(extra.get("expert_reviewed", False)),
        "statement_kinds": {
            "text": "paraphrase_of_source" if text_kind == "paraphrase" else f"{text_kind}_of_source",
            "notes": "editorial_summary",
        },
    }
    if "legislation.gov.au" in (source_url or ""):
        out["attribution"] = frl_attribution(std.get("verified_on"), changed=text_kind != "excerpt")
    return out


def frl_attribution(verified_on: Optional[str], changed: bool) -> str:
    """Attribution wording the Federal Register's CC BY 4.0 terms require (legislation.gov.au/terms-of-use)."""
    try:
        d = date.fromisoformat(verified_on or "")
        when = f"{d.day} {d:%B %Y}"
    except ValueError:
        when = "the date shown in verified_on"
    if changed:
        return (f"Based on content from the Federal Register of Legislation at {when}. For the latest information on "
                "Australian Government legislation please go to https://www.legislation.gov.au.")
    return (f"Sourced from the Federal Register of Legislation at {when}. For the latest information on Australian "
            "Government law please go to https://www.legislation.gov.au.")


def domain_sectors(domain: str) -> List[str]:
    """Sectors a domain pack covers; raises ValueError listing valid domains when unknown."""
    d = resolve_domain(domain)
    if not d:
        valid = ", ".join(x["id"] for x in load_domains())
        raise ValueError(f"Unknown domain '{domain}'. Valid: {valid}.")
    return d["sectors"]


def _supported_codes() -> str:
    return ", ".join(r["code"] for r in list_instrument_rows())


def list_standards() -> List[Dict[str, Any]]:
    """List every instrument in the registry (kept for backward compatibility; see list_instruments)."""
    return [
        {
            "code": r["code"],
            "title": r["title"],
            "short_name": r["short_name"],
            "regulator": r["regulator"],
            "status": r["status"],
            "effective_date": r["effective_date"],
            "legislative_instrument": r["legislative_instrument"],
        }
        for r in list_instrument_rows()
    ]


def list_instruments(
    regulator: Optional[str] = None, sector: Optional[str] = None, domain: Optional[str] = None
) -> Dict[str, Any]:
    """List instruments with provenance, filtered by regulator ('ASIC'), sector ('life_insurance') or domain."""
    rows = list_instrument_rows()
    if regulator:
        rows = [r for r in rows if regulator.lower() in r["regulator"].lower()]
    if sector:
        rows = [r for r in rows if sector in r["sectors"]]
    if domain:
        wanted = set(domain_sectors(domain))
        rows = [r for r in rows if wanted & set(r["sectors"])]
    return {
        "total": len(rows),
        "instruments": [
            {
                "code": r["code"],
                "title": r["title"],
                "regulator": r["regulator"],
                "instrument_type": r["instrument_type"],
                "status": r["status"],
                "enforceability": r["enforceability"],
                "sectors": r["sectors"],
                "clause_count": r["clause_count"],
                "text_kind": r["text_kind"],
                "source_url": r["source_url"],
                "verified_on": r["verified_on"] or "not yet verified",
            }
            for r in rows
        ],
        "disclaimer": DISCLAIMER,
    }


def red_team_coverage(sectors) -> Dict[str, Any]:
    """Pack categories and scenarios that red-team runs use for these sectors (rules-based insurance and banking
    categories are listed by get_coverage_map)."""
    from src.rules import packs

    cats = packs.categories_for(sectors)
    return {"pack_categories": sorted(cats), "pack_scenarios": len(packs.scenarios_for(sectors)),
            "detection": "semantic judge (REVIEW flags for human confirmation)" if cats else "rules only"}


def list_domains() -> Dict[str, Any]:
    """Each industry domain pack with its regulators, coverage level, known gaps and corpus freshness."""
    rows = list_instrument_rows()
    out = []
    for d in load_domains():
        mine = [r for r in rows if set(d["sectors"]) & set(r["sectors"])]
        dates = sorted(r["verified_on"] for r in mine if r["verified_on"])
        out.append({
            **{k: d.get(k) for k in ("id", "name", "aliases", "sectors", "coverage", "regulators", "scope_notes", "known_gaps")},
            "instrument_count": len(mine),
            "unverified_instruments": sorted(r["code"] for r in mine if not r["verified_on"]),
            "oldest_verified_on": dates[0] if dates else None,
            "expert_reviewed": bool(mine) and all(r["extra"].get("expert_reviewed") for r in mine),
            "red_team": red_team_coverage(frozenset(d["sectors"])),
        })
    return {
        "total": len(out),
        "domains": out,
        "not_yet_covered": "Industries without a domain pack have no corpus here; absence of results is not absence of obligations.",
        "disclaimer": DISCLAIMER,
    }


def get_standard_overview(standard_code: str) -> Dict[str, Any]:
    """Get metadata, legal source, scope, provenance and summary of any instrument in the registry."""
    std = get_standard_by_code(standard_code)
    if not std:
        return {"error": f"Instrument '{standard_code}' not found. Supported instruments: {_supported_codes()}."}
    return std


def lookup_specific_clause(standard_code: str, clause_number: str) -> Dict[str, Any]:
    """Retrieve the obligation text, subclauses and notes for a clause, by citation ('13', 'APP 6') or anchor."""
    std = get_standard_by_code(standard_code)
    if not std:
        return {"error": f"Instrument '{standard_code}' not found. Supported instruments: {_supported_codes()}."}
    clause = get_clause_by_number(std["code"], clause_number)
    if not clause:
        return {"error": f"Clause '{clause_number}' not found in '{std['code']}'."}
    return {
        "id": clause["id"],
        "standard": clause["standard_code"],
        "regulator": std["regulator"],
        "clause_number": clause["clause_number"],
        "section": clause["section_name"],
        "heading": clause["heading"],
        "statutory_text": clause["text"],
        "text_kind": std["text_kind"],
        "subclauses": clause["subclauses"],
        "is_mandatory": clause["is_mandatory"],
        "notification_trigger": clause["notification_trigger"],
        "notes_and_guidance": clause["notes"],
        "obligation_type": clause.get("obligation_type"),
        "agent_relevance": clause.get("agent_relevance"),
        "anchor": clause.get("anchor"),
        "source_url": clause.get("source_url") or std["source_url"],
        "verified_on": std["verified_on"] or "not yet verified",
        "evidence": evidence(std, clause),
        "disclaimer": DISCLAIMER,
    }
