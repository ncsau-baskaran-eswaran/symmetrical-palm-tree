"""Full-text search across the regulatory instrument registry."""

from typing import Any, Dict, Optional
from src.db import search_clauses


def execute_search(
    query: str,
    standard_code: Optional[str] = None,
    limit: int = 5,
    regulator: Optional[str] = None,
    sector: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a ranked search over instrument clauses, with optional instrument, regulator and sector filters."""
    results = search_clauses(query=query, standard_code=standard_code, limit=limit, regulator=regulator, sector=sector)

    formatted = []
    for r in results:
        formatted.append({
            "id": r["id"],
            "standard": r["standard_code"],
            "clause_number": r["clause_number"],
            "section": r["section_name"],
            "heading": r["heading"],
            "text": r["text"],
            "subclauses": r["subclauses"][:3] if r.get("subclauses") else [],
            "notification_trigger": r.get("notification_trigger"),
            "notes": r.get("notes")
        })

    return {
        "query": query,
        "standard_filter": standard_code or "all",
        "regulator_filter": regulator or "all",
        "sector_filter": sector or "all",
        "total_results": len(formatted),
        "results": formatted
    }
