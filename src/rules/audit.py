"""Runs the rule catalogue (and optionally the semantic judge) over one agent interaction."""

import re
from functools import lru_cache
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from src.config import scoped_sectors
from src.db import get_clause_by_number, get_standard_by_code
from src.rules.catalog import JUDGE_ONLY_CATEGORIES, RULES
from src.rules.engine import ALL_SECTORS, BANK, GI, INSURANCE, LIFE, PHI, Hit, Ref, evaluate_rule
from src.rules import judge as judge_module
from src.tools.notifications import assess_notification_requirements, assess_regulatory_obligations

DEFAULT_MATERIALITY_THRESHOLD = 50_000.0

_SECTOR_ALIASES = {
    "gi": GI, "general": GI, "general_insurance": GI, "general insurance": GI,
    "life": LIFE, "life_insurance": LIFE, "life insurance": LIFE,
    "phi": PHI, "health": PHI, "private_health": PHI, "private_health_insurance": PHI, "private health insurance": PHI,
    "banking": BANK, "bank": BANK, "adi": BANK, "lending": BANK,
}

# Role keywords, checked in order. Unknown roles run every sector so nothing is silently skipped.
_ROLE_SECTORS: Tuple[Tuple[str, FrozenSet[str]], ...] = (
    (r"phi|health|member|hospital|extras", frozenset({PHI})),
    (r"life|tpd|income_protection|ip_claims|trauma|death|salary_continuance", frozenset({LIFE})),
    (r"lending|loan|payment|bank|credit|mortgage|deposit", frozenset({BANK})),
    (r"claim|underwrit|policy|motor|home|travel|property|strata|insurance", frozenset({GI})),
)


def resolve_sectors(agent_role: str, sector: Optional[str] = None) -> FrozenSet[str]:
    if sector:
        s = sector.lower().strip()
        if s in ("insurance", "insurer", "all_insurance"):
            return INSURANCE
        if s in ("all", "any"):
            return ALL_SECTORS
        if s in _SECTOR_ALIASES:
            return frozenset({_SECTOR_ALIASES[s]})
        for key, value in _SECTOR_ALIASES.items():
            if key in s:
                return frozenset({value})
    role = (agent_role or "").lower()
    for pattern, sectors in _ROLE_SECTORS:
        if re.search(pattern, role):
            return sectors
    return ALL_SECTORS


@lru_cache(maxsize=512)
def _resolve_ref(code: str, clause: str) -> Dict[str, Any]:
    inst = get_standard_by_code(code)
    cl = get_clause_by_number(inst["code"], clause) if inst else None
    return {
        "instrument": inst["code"] if inst else code,
        "regulator": inst["regulator"] if inst else None,
        "clause": cl["clause_number"] if cl else clause,
        "heading": cl["heading"] if cl else None,
        "resolved": bool(cl),
    }


def describe_obligation(ref: Ref) -> Dict[str, Any]:
    return {**_resolve_ref(ref.code, ref.clause), "why": ref.why}


def _citation(ob: Dict[str, Any]) -> str:
    # Guide paragraphs already carry the instrument ("RG 271.27"), so don't repeat it.
    if str(ob["clause"]).startswith(ob["instrument"]):
        return str(ob["clause"])
    return f"{ob['instrument']} {ob['clause']}".strip()


def _violation(hit: Hit) -> Dict[str, Any]:
    rule = hit.rule
    obligations = [describe_obligation(o) for o in hit.obligations]
    primary = obligations[0] if obligations else {"instrument": "", "clause": ""}
    return {
        "standard": rule.legacy_standard or primary["instrument"],
        "clause": rule.legacy_clause or primary["clause"],
        "category": rule.category,
        "severity": hit.severity,
        "finding": rule.finding,
        "apra_risk": rule.risk,
        "regulatory_risk": rule.risk,
        "statutory_remediation": rule.remediation,
        "rule_id": rule.id,
        "family": rule.family,
        "evidence": hit.evidence,
        "material_exposure": hit.material,
        "obligations": obligations,
        "citations": [_citation(o) for o in obligations],
        "detection": "rule",
    }


_ROLE_ALIASES = {"customer": "customer", "user": "customer", "agent": "agent", "assistant": "agent"}


def _normalise_turns(prior_turns: Optional[List[Dict[str, str]]]) -> List[Tuple[str, str]]:
    """Valid (role, text) pairs in order; malformed entries are skipped rather than failing the screen."""
    turns: List[Tuple[str, str]] = []
    for t in prior_turns or []:
        role = _ROLE_ALIASES.get(str(t.get("role", "")).lower().strip()) if isinstance(t, dict) else None
        text = str(t.get("text", "")) if role else ""
        if role and text.strip():
            turns.append((role, text))
    return turns


def run_audit(
    agent_role: str,
    user_prompt: str,
    agent_response: str,
    context: Optional[Dict[str, Any]] = None,
    sector: Optional[str] = None,
    prior_turns: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    context = context or {}
    explicit = sector or context.get("sector")
    sectors = resolve_sectors(agent_role, explicit)
    if not explicit:
        # Inferred sectors are narrowed to the server's scope (GUARDIAN_SECTORS). A role that only makes sense
        # outside the scope (a lending agent on an insurance-only server) keeps its own sector.
        sectors = (sectors & scoped_sectors()) or sectors
    threshold = float(context.get("materiality_threshold", DEFAULT_MATERIALITY_THRESHOLD))
    prompt_lower = (user_prompt or "").lower()
    resp_lower = (agent_response or "").lower()

    # Conversation history: gates see every customer turn, omission rules also see earlier agent turns.
    turns = _normalise_turns(prior_turns)
    prior_agent_lower = "\n".join(text for role, text in turns if role == "agent").lower()
    if turns:
        prompt_lower = "\n".join([text for role, text in turns if role == "customer"] + [user_prompt or ""]).lower()
    conversation_info = {"conversation": {"turns_considered": len(turns)}} if prior_turns else {}

    applicable = [r for r in RULES if r.sectors & sectors]
    breaches: List[Hit] = []
    reviews: List[Hit] = []
    seen_categories = set()
    for rule in applicable:
        hit = evaluate_rule(rule, prompt_lower, resp_lower, context, sectors, threshold, prior_agent_lower)
        if not hit or rule.category in seen_categories:
            continue
        seen_categories.add(rule.category)
        (reviews if rule.review_only else breaches).append(hit)

    violations = [_violation(h) for h in breaches]
    review_flags = [_violation(h) for h in reviews]

    judge_result = judge_module.maybe_judge(
        agent_role=agent_role,
        user_prompt=user_prompt,
        agent_response=agent_response,
        sectors=sectors,
        rule_categories=[r.category for r in applicable],
        extra_categories=list(JUDGE_ONLY_CATEGORIES),
        already_found={v["category"] for v in violations},
        context=context,
        prior_turns=turns,
    )
    for jf in judge_result.get("findings", []):
        if jf["category"] in {v["category"] for v in violations}:
            for v in violations:
                if v["category"] == jf["category"]:
                    v["corroborated_by_judge"] = True
            continue
        review_flags.append(judge_module.as_review_flag(jf, sectors))

    # Severity never downgrades; review flags do not raise it.
    order = {"CLEAN": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    severity = "CLEAN"
    for v in violations:
        if order.get(v["severity"], 0) > order[severity]:
            severity = v["severity"]

    triggers: List[str] = []
    for h in breaches:
        for t in h.rule.triggers + (h.rule.material_triggers if h.material else ()):
            if t not in triggers:
                triggers.append(t)

    # One combined APRA assessment, so a later finding can never overwrite an earlier notification.
    is_cyber = "apra_cps234_35" in triggers
    is_material = is_cyber or "apra_cps230_33" in triggers
    notification_details = None
    if is_material:
        categories = ", ".join(v["category"] for v in violations)
        notification_details = assess_notification_requirements(
            incident_type=f"Autonomous {agent_role} interaction: {categories}",
            is_cyber_or_infosec=is_cyber,
            exceeds_tolerance=False,
            is_material_impact=True,
            notified_to_other_regulators=is_cyber,
        )

    regulatory = assess_regulatory_obligations(
        triggers,
        sectors=sectors,
        detected_at=context.get("detected_at"),
        entity_profile=context.get("entity_profile"),
    ) if triggers else None

    obligations_engaged: List[Dict[str, Any]] = []
    for v in violations:
        for ob in v["obligations"]:
            if ob not in obligations_engaged:
                obligations_engaged.append({k: ob[k] for k in ("instrument", "regulator", "clause", "heading")})
    deduped, keys = [], set()
    for ob in obligations_engaged:
        key = (ob["instrument"], ob["clause"])
        if key not in keys:
            keys.add(key)
            deduped.append(ob)

    if violations:
        verdict, screen = "FAILED", "BREACH"
        summary = (
            f"Detected {len(violations)} breach pattern(s) engaging {len(deduped)} obligation(s) across "
            f"{len({o['regulator'] for o in deduped if o['regulator']})} regulator(s). Overall risk level: {severity}."
        )
    elif review_flags:
        verdict, screen = "PASSED", "REVIEW"
        summary = (
            f"No breach pattern detected, but {len(review_flags)} item(s) need human review. "
            "This is a screen, not confirmation that the interaction complies."
        )
    else:
        verdict, screen = "PASSED", "NO_PATTERN_DETECTED"
        summary = (
            "No breach pattern detected for the rules that apply to this role and sector. This is a heuristic screen, "
            "not confirmation that the interaction complies; reworded breaches can evade it."
        )

    return {
        "audit_verdict": verdict,
        "screen_result": screen,
        "risk_severity": severity,
        "agent_role": agent_role,
        "sectors_evaluated": sorted(sectors),
        "summary": summary,
        "assessment_basis": "heuristic_pattern_match" if not judge_result.get("enabled") else "heuristic_pattern_match+semantic_judge",
        "apra_violations": violations,
        "review_flags": review_flags,
        "obligations_engaged": deduped,
        "statutory_apra_reporting_required": notification_details is not None,
        "apra_reporting_assessment": notification_details,
        "regulatory_reporting": regulatory,
        "coverage_scope": {
            "rules_evaluated": len(applicable),
            "rule_families": sorted({r.family for r in applicable}),
            "judge": judge_result.get("status", "disabled"),
        },
        **conversation_info,
        "governance_advisory": (
            "Under CPS 230 Paragraph 19, CPS 234 Paragraph 13 and the Financial Accountability Regime, the Board and "
            "accountable persons remain responsible for risks arising from autonomous agents in production."
        ),
    }
