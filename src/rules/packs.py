"""Red-team packs: breach categories and adversarial scenarios per industry, loaded from src/data/redteam/*.json.

Insurance and banking detection lives in code (src/rules/catalog.py) because its rules are regular expressions.
Every other industry is data: a pack lists the categories the semantic judge may report, the obligations each one
cites (they must resolve in the instrument registry; tests/test_redteam_packs.py enforces it) and the scenarios
that probe for them. A pack applies to the sectors it names; `baseline.json` holds categories shared by them all.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Tuple

from src.rules.engine import Ref

PACKS_DIR = Path(__file__).resolve().parent.parent / "data" / "redteam"


@lru_cache(maxsize=1)
def load_packs() -> Tuple[Dict[str, Any], ...]:
    """Every pack, in file order (tests/test_redteam_packs.py checks ids and citations)."""
    packs = []
    for path in sorted(PACKS_DIR.glob("*.json")):
        with open(path, "r", encoding="utf-8") as f:
            pack = json.load(f)
        pack["sectors"] = frozenset(pack["sectors"])
        packs.append(pack)
    return tuple(packs)


def pack_sectors() -> FrozenSet[str]:
    return frozenset().union(*(p["sectors"] for p in load_packs())) if load_packs() else frozenset()


def _packs_for(sectors: FrozenSet[str]) -> List[Dict[str, Any]]:
    return [p for p in load_packs() if p["sectors"] & sectors]


def categories_for(sectors: FrozenSet[str]) -> Dict[str, Dict[str, Any]]:
    """Pack categories that apply to these sectors, keyed by id. An industry pack overrides the baseline's entry."""
    out: Dict[str, Dict[str, Any]] = {}
    for pack in sorted(_packs_for(sectors), key=lambda p: p["id"] != "baseline"):
        for cat in pack["categories"]:
            out[cat["id"]] = {**cat, "pack": pack["id"]}
    return out


def refs_for(category: Dict[str, Any], sectors: FrozenSet[str]) -> List[Ref]:
    """Obligations a pack category cites."""
    return [Ref(ob["code"], ob["clause"], ob.get("why", ""), sectors) for ob in category.get("obligations", [])]


def scenarios_for(sectors: FrozenSet[str]) -> List[Dict[str, Any]]:
    """Adversarial scenarios from the packs that apply, tagged with the pack and its first sector."""
    out = []
    for pack in _packs_for(sectors):
        for sc in pack.get("scenarios", []):
            out.append({**sc, "pack": pack["id"], "sector": sorted(pack["sectors"] & sectors)[0]})
    return out


def reviewer_for(sectors: FrozenSet[str]) -> str:
    """Judge persona: the industry packs' reviewer descriptions, or a neutral one."""
    names = sorted({p["reviewer"] for p in _packs_for(sectors) if p["id"] != "baseline" and p.get("reviewer")})
    return " and ".join(names) if names else "Australian regulatory compliance reviewer"
