"""Provenance for audit results: which engine, corpus, rules and judge produced a decision, and when.

Everything here is deterministic for identical inputs and identical corpus/rules, except `screened_at`. A
`finding_id` therefore stays stable across reruns, so a recorded decision can be tied back to the exact rule set.
"""

import hashlib
import json
import time
from datetime import datetime, timezone
from importlib import metadata
from typing import Any, Dict, Iterable, Mapping, Optional

from src import db
from src.rules.catalog import JUDGE_ONLY_CATEGORIES, RULES
from src.rules.engine import P, Ref, Rule

ENGINE_NAME = "guardian-compliance-mcp"
_FALLBACK_VERSION = "0.3.0"  # keep in step with pyproject.toml
SHORT = 12


def _engine_version() -> str:
    try:
        return metadata.version(ENGINE_NAME)
    except metadata.PackageNotFoundError:
        return _FALLBACK_VERSION


def _ref(ref: Ref) -> list:
    return [ref.code, ref.clause, sorted(ref.sectors)]


def _pattern(p: Any) -> list:
    return [p.regex, p.negation_aware] if isinstance(p, P) else [p, True]


def _rule(rule: Rule) -> list:
    return [
        rule.id, rule.category, rule.family, sorted(rule.sectors),
        [_pattern(p) for p in rule.response_patterns],
        list(rule.prompt_gate), list(rule.prompt_exclude), list(rule.requires_absent),
        [_ref(o) for o in rule.obligations],
        rule.severity, rule.material_severity, rule.always_material, rule.review_only, rule.refusal_veto,
        # Triggers decide which reporting deadlines a finding starts, so they are part of a rule's behaviour.
        list(rule.triggers), list(rule.material_triggers), rule.context_terms_key,
    ]


def compute_rules_hash(rules: Iterable[Rule], judge_only: Mapping[str, Any]) -> str:
    """sha256 over a canonical serialisation of the rules and judge-only categories (full hex digest)."""
    canon = {
        "rules": [_rule(r) for r in rules],
        "judge_only": {k: [desc, [_ref(o) for o in refs]] for k, (desc, refs) in sorted(judge_only.items())},
    }
    return hashlib.sha256(json.dumps(canon, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# Rules are import-time constants, so hash once.
RULES_HASH = compute_rules_hash(RULES, JUDGE_ONLY_CATEGORIES)
ENGINE_VERSION = _engine_version()


def corpus_hash_short() -> str:
    """Corpus hash recorded in the registry database, falling back to hashing the corpus files."""
    return (db.stored_corpus_hash() or db.corpus_hash())[:SHORT]


def finding_id(rule_id: str, category: str, evidence: str, agent_response: str, rules_hash: str = RULES_HASH) -> str:
    response_digest = hashlib.sha256((agent_response or "").encode()).hexdigest()
    raw = "|".join((rules_hash, rule_id, category, evidence or "", response_digest))
    return hashlib.sha256(raw.encode()).hexdigest()[:SHORT]


def build_provenance(judge_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    judge_result = judge_result or {}
    enabled = bool(judge_result.get("enabled"))
    return {
        "engine": {"name": ENGINE_NAME, "version": ENGINE_VERSION},
        "corpus_hash": corpus_hash_short(),
        "rules_hash": RULES_HASH[:SHORT],
        "schema_version": db.SCHEMA_VERSION,
        "judge": {
            "provider": judge_result.get("provider") or "unknown" if enabled else "disabled",
            "model": judge_result.get("model") or "unknown" if enabled else "disabled",
        },
        "screened_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def attach_provenance(result: Dict[str, Any], judge_result: Dict[str, Any], agent_response: str, started: float) -> Dict[str, Any]:
    """Add provenance, per-finding ids and timing to an audit result. `started` is a time.perf_counter() reading."""
    total = (time.perf_counter() - started) * 1000
    judge_ms = float(judge_result.get("elapsed_ms", 0.0)) if judge_result.get("enabled") else 0.0
    rule_version = RULES_HASH[:SHORT]
    for item in list(result.get("apra_violations", [])) + list(result.get("review_flags", [])):
        item["finding_id"] = finding_id(item.get("rule_id", ""), item.get("category", ""), item.get("evidence", ""), agent_response)
        item["rule_version"] = rule_version
    result["provenance"] = build_provenance(judge_result)
    result["timing_ms"] = {
        "rules": round(max(total - judge_ms, 0.0), 3),
        "judge": round(judge_ms, 3),
        "total": round(total, 3),
    }
    return result
