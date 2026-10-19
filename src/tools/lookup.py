"""Lookup tools for regulatory instruments (APRA, ASIC, OAIC, Codes, health law) and their clauses."""

from typing import Any, Dict, List, Optional
from src.db import get_standard_by_code, get_clause_by_number, list_instrument_rows


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


def list_instruments(regulator: Optional[str] = None, sector: Optional[str] = None) -> Dict[str, Any]:
    """List instruments with provenance, optionally filtered by regulator ('ASIC') or sector ('life_insurance')."""
    rows = list_instrument_rows()
    if regulator:
        rows = [r for r in rows if regulator.lower() in r["regulator"].lower()]
    if sector:
        rows = [r for r in rows if sector in r["sectors"]]
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
        "disclaimer": (
            "Obligations are paraphrased summaries for screening and triage, not legal advice. "
            "Always confirm against the source instrument."
        ),
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
        "source_url": std["source_url"],
        "verified_on": std["verified_on"] or "not yet verified",
    }
