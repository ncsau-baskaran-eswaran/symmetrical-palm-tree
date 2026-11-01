"""Full-text search across the regulatory instrument registry."""

from typing import Any, Dict, Optional
from src.db import search_clauses
from src.tools.lookup import DISCLAIMER, domain_sectors, evidence


def execute_search(
    query: str,
    standard_code: Optional[str] = None,
    limit: int = 5,
    regulator: Optional[str] = None,
    sector: Optional[str] = None,
    domain: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a ranked search over instrument clauses, with optional instrument, regulator, sector and domain filters."""
    sectors = domain_sectors(domain) if domain else None
    results = search_clauses(
        query=query, standard_code=standard_code, limit=limit, regulator=regulator, sector=sector, sectors=sectors
    )

    formatted = []
    for r in results:
        std = {k[4:]: v for k, v in r.items() if k.startswith("std_")}
        formatted.append({
            "id": r["id"],
            "standard": r["standard_code"],
            "regulator": std["regulator"],
            "clause_number": r["clause_number"],
            "section": r["section_name"],
            "heading": r["heading"],
            "text": r["text"],
            "subclauses": r["subclauses"][:3] if r.get("subclauses") else [],
            "notification_trigger": r.get("notification_trigger"),
            "notes": r.get("notes"),
            "evidence": evidence(std, r),
        })

    out = {
        "query": query,
        "standard_filter": standard_code or "all",
        "regulator_filter": regulator or "all",
        "sector_filter": sector or "all",
        "domain_filter": domain or "all",
        "total_results": len(formatted),
        "supporting_evidence": bool(formatted),
        "results": formatted,
        "disclaimer": DISCLAIMER,
    }
    if not formatted:
        out["determination"] = (
            "No supporting evidence in the loaded corpus for this query and these filters. This does not mean no "
            "obligation exists: the corpus covers only the instruments listed by list_instruments."
        )
    return out
