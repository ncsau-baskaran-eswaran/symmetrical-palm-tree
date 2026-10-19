"""Rule engine: evaluates an agent interaction against the obligation-mapped rule catalogue.

A rule fires when a response pattern matches an affirmative span (not negated, not conditional), any prompt gate
matches, no prompt exclusion matches, and none of the response's "requires_absent" signals are present. Rules
marked `review_only` describe omissions (for example a complaint that was never acknowledged); they raise a REVIEW
flag rather than a breach, because a single turn cannot prove the agent never handled it.

Multi-turn: prompt gates and exclusions see the customer's whole conversation (prior turns plus the current message),
while response patterns only ever see the reply being screened. Omission rules (complaints, vulnerability) also
credit what the agent said in earlier turns.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple, Union

GI = "general_insurance"
LIFE = "life_insurance"
PHI = "private_health_insurance"
BANK = "banking"
INSURANCE: FrozenSet[str] = frozenset({GI, LIFE, PHI})
ALL_SECTORS: FrozenSet[str] = frozenset({GI, LIFE, PHI, BANK})

# A negation inside the matched span ("I have not approved your loan") is a refusal, not a commitment.
NEGATION_PATTERN = r"\b(not|never|cannot|unable)\b|n't\b"

# Negation or conditionality earlier in the same sentence ("I can't confirm your claim is approved",
# "once your claim is approved, we will pay") also turns a match into a non-commitment.
_PRECEDING_QUALIFIER = re.compile(
    r"\b(not|never|no|cannot|unable|if|once|whether|until|unless|pending|before|when)\b|n't\b|subject to"
)
# Idioms that contain a negation word but are affirmative ("No problem, your claim has been approved").
_AFFIRMATIVE_IDIOMS = re.compile(r"\b(no problem|no worries|no dramas|not a problem|no trouble|no doubt|don't worry|do not worry|no need to worry|not to worry)\b")
_SENTENCE_BREAK = re.compile(r"[.!?;\n]")


@dataclass(frozen=True)
class P:
    """A response pattern. `negation_aware=False` for phrasings that are inherently negative ("claim is declined")."""
    regex: str
    negation_aware: bool = True


@dataclass(frozen=True)
class Ref:
    """A pointer to an obligation in the registry: instrument code plus clause number or anchor."""
    code: str
    clause: str
    why: str = ""
    sectors: FrozenSet[str] = ALL_SECTORS


@dataclass(frozen=True)
class Rule:
    id: str
    category: str
    family: str
    sectors: FrozenSet[str]
    response_patterns: Tuple[Union[P, str], ...]
    obligations: Tuple[Ref, ...]
    finding: str
    risk: str
    remediation: str
    prompt_gate: Tuple[str, ...] = ()
    prompt_exclude: Tuple[str, ...] = ()
    requires_absent: Tuple[str, ...] = ()
    refusal_veto: bool = False
    severity: str = "HIGH"
    material_severity: Optional[str] = None
    always_material: bool = False
    review_only: bool = False
    triggers: Tuple[str, ...] = ()
    material_triggers: Tuple[str, ...] = ()
    legacy_standard: Optional[str] = None
    legacy_clause: Optional[str] = None
    context_terms_key: Optional[str] = None


@dataclass
class Hit:
    rule: Rule
    evidence: str
    material: bool
    severity: str
    obligations: List[Ref] = field(default_factory=list)


# Families whose requires_absent signals describe something the agent should have done at some point in the
# conversation (acknowledge the complaint, offer support, give AFCA details). For these, an earlier agent turn that
# already did it clears the current reply. Every other rule's requires_absent is a property of the reply itself
# (a hedge, a warning, a verification step) and is checked against the current response only.
OMISSION_FAMILIES: FrozenSet[str] = frozenset({"complaints", "vulnerability"})

_REFUSALS = ("unable to", "cannot", "will not", "prohibited", "decline to", "restricted", "cannot be disclosed", "can't share", "not able to")


def _is_qualified(text: str, start: int, span: str) -> bool:
    if re.search(NEGATION_PATTERN, span):
        return True
    sentence_start = 0
    for m in _SENTENCE_BREAK.finditer(text, 0, start):
        sentence_start = m.end()
    window = text[max(sentence_start, start - 90):start]
    window = _AFFIRMATIVE_IDIOMS.sub(" ", window)
    return bool(_PRECEDING_QUALIFIER.search(window))


def first_affirmative_match(patterns: Sequence[Union[P, str]], text: str) -> Optional[str]:
    """Return the first matched span that is not negated or conditional, else None."""
    for pat in patterns:
        p = pat if isinstance(pat, P) else P(pat)
        for m in re.finditer(p.regex, text):
            if not p.negation_aware or not _is_qualified(text, m.start(), m.group(0)):
                return m.group(0)
    return None


_AMOUNT = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k|m|million|thousand)?\b", re.IGNORECASE)
_BARE_AMOUNT = re.compile(r"\b(\d{1,3}(?:,\d{3})+)\b")


def largest_amount(*texts: str) -> float:
    """Largest dollar figure mentioned ("$85,000", "$250k", "$1.2 million", "250,000")."""
    best = 0.0
    for text in texts:
        for m in _AMOUNT.finditer(text):
            value = float(m.group(1).replace(",", ""))
            unit = (m.group(2) or "").lower()
            if unit in ("k", "thousand"):
                value *= 1_000
            elif unit in ("m", "million"):
                value *= 1_000_000
            best = max(best, value)
        for m in _BARE_AMOUNT.finditer(text):
            best = max(best, float(m.group(1).replace(",", "")))
        if re.search(r"\bmillion\b", text):
            best = max(best, 1_000_000)
    return best


def evaluate_rule(
    rule: Rule,
    prompt_lower: str,
    resp_lower: str,
    context: Dict[str, Any],
    sectors: FrozenSet[str],
    materiality_threshold: float,
    prior_agent_lower: str = "",
) -> Optional[Hit]:
    # prompt_lower is the customer's text (across prior turns when screening a conversation); resp_lower is only the
    # current reply, so a breach is always attributed to the response being screened.
    if rule.prompt_gate and not any(re.search(g, prompt_lower) for g in rule.prompt_gate):
        return None
    if rule.prompt_exclude and any(re.search(x, prompt_lower) for x in rule.prompt_exclude):
        return None
    absent_text = f"{prior_agent_lower}\n{resp_lower}" if prior_agent_lower and rule.family in OMISSION_FAMILIES else resp_lower
    if rule.requires_absent and any(re.search(a, absent_text) for a in rule.requires_absent):
        return None
    if rule.refusal_veto and any(r in resp_lower for r in _REFUSALS):
        return None

    evidence = first_affirmative_match(rule.response_patterns, resp_lower) if rule.response_patterns else ""
    if rule.context_terms_key:
        # Caller-supplied terms (for example a TMD's excluded classes) must appear in the prompt.
        terms = [str(t).lower() for t in context.get(rule.context_terms_key, []) if str(t).strip()]
        if not terms or not any(t in prompt_lower for t in terms):
            return None
    if evidence is None:
        return None

    exposure = max(
        float(context.get("claim_amount", 0) or 0),
        float(context.get("exposure_amount", 0) or 0),
        largest_amount(resp_lower, prompt_lower),
    )
    material = rule.always_material or (rule.material_severity is not None and exposure >= materiality_threshold)
    severity = rule.material_severity if (material and rule.material_severity) else rule.severity
    obligations = [o for o in rule.obligations if o.sectors & sectors]
    return Hit(rule=rule, evidence=evidence, material=material, severity=severity, obligations=obligations)
