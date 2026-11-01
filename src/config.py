"""Startup configuration: which toolsets are exposed and which insurance sectors the server is scoped to.

Follows the pattern of the large public MCP servers (GitHub toolsets, Supabase feature groups and project
scoping): one server, a lean default surface, and opt-in groups for specialist work.

    GUARDIAN_TOOLSETS   comma-separated toolsets, or "all". Default: "core,reference".
                        core        screening, triage, deadlines, coverage
                        reference   rulebook search and clause lookup
                        governance  CPS 230 requirements, architecture and code inspection
                        redteam     adversarial test cases and probes of external agents
                        demo        simulations against the built-in mock agent
                        legacy      pre-0.3 tool names and apra:// resources, kept for one release
    GUARDIAN_SECTORS    comma-separated industries, e.g. gi, life, phi, insurance, banking, superannuation,
                        energy_retail, telecommunications, water, public_sector, commercial. Default: gi,life,phi.
                        Scopes prompts, coverage, test cases, red-team defaults and inferred audit sectors.
"""

import os
from typing import FrozenSet, Optional

ALL_TOOLSETS = ("core", "reference", "governance", "redteam", "demo", "legacy")
DEFAULT_TOOLSETS = ("core", "reference")

_SECTOR_NAMES = {
    "gi": "general_insurance", "general": "general_insurance", "general_insurance": "general_insurance",
    "life": "life_insurance", "life_insurance": "life_insurance",
    "phi": "private_health_insurance", "health": "private_health_insurance", "private_health_insurance": "private_health_insurance",
    "banking": "banking", "bank": "banking", "adi": "banking",
    "superannuation": "superannuation", "super": "superannuation", "rse": "superannuation",
    "energy_retail": "energy_retail", "energy": "energy_retail",
    "telecommunications": "telecommunications", "telco": "telecommunications",
    "water": "water",
    "public_sector": "public_sector", "government": "public_sector",
    "commercial": "commercial", "retail": "commercial",
}
INSURANCE = frozenset({"general_insurance", "life_insurance", "private_health_insurance"})


def _split(value: Optional[str]) -> list:
    return [v.strip().lower() for v in (value or "").split(",") if v.strip()]


def enabled_toolsets(value: Optional[str] = None) -> FrozenSet[str]:
    raw = _split(value if value is not None else os.environ.get("GUARDIAN_TOOLSETS"))
    if not raw:
        return frozenset(DEFAULT_TOOLSETS)
    if "all" in raw:
        return frozenset(ALL_TOOLSETS)
    unknown = [t for t in raw if t not in ALL_TOOLSETS]
    if unknown:
        raise ValueError(f"Unknown GUARDIAN_TOOLSETS value(s): {', '.join(unknown)}. Valid: {', '.join(ALL_TOOLSETS)}, all.")
    return frozenset(raw)


def scoped_sectors(value: Optional[str] = None) -> FrozenSet[str]:
    raw = _split(value if value is not None else os.environ.get("GUARDIAN_SECTORS"))
    if not raw:
        return INSURANCE
    unknown = [s for s in raw if s not in _SECTOR_NAMES and s != "insurance"]
    if unknown:
        valid = ", ".join(sorted(set(_SECTOR_NAMES) | {"insurance"}))
        raise ValueError(f"Unknown GUARDIAN_SECTORS value(s): {', '.join(unknown)}. Valid: {valid}.")
    return frozenset().union(*(INSURANCE if s == "insurance" else {_SECTOR_NAMES[s]} for s in raw))


def is_scoped() -> bool:
    """True when the operator narrowed the sectors explicitly (rather than the insurance default)."""
    return bool(_split(os.environ.get("GUARDIAN_SECTORS")))
