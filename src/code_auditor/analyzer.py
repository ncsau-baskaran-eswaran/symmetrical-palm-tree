"""AST-based code-aware analyzer for APRA agent-control evidence.

Status taxonomy (deliberately honest, per the codex + agy review):
  EXPOSURE            a concrete risk found in the source (e.g. a hardcoded TFN)
  CONTROL_VERIFIED    the control's code path is actually wired in
  CONTROL_INDICATOR   a control pattern is present but not provably reached
  CONTROL_MISSING     a relevant control is absent on a path that needs it
  UNVERIFIABLE_LOCALLY not determinable from this source (may live upstream)

Findings map to clause *relevance*, not compliance verdicts.
"""

import ast
import os
import re
from typing import Any, Dict, List, Optional

# --- detection patterns -----------------------------------------------------

SENSITIVE_PATTERNS = [
    ("TFN", re.compile(r"\bTFN\b|\b\d{3}\s\d{3}\s\d{3}\b")),
    ("Medicare number", re.compile(r"Medicare|\b\d{4}\s\d{5}\s\d\b")),
    ("BSB", re.compile(r"\bBSB\b|\b\d{3}-\d{3}\b")),
    ("Credit card", re.compile(r"\b\d{4}\s\d{4}\s\d{4}\s\d{4}\b")),
    ("Account number", re.compile(r"Acct\s*#|Account\s*#|account\s\d{6,}")),
]
SECRET_PATTERNS = [
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Private key", re.compile(r"BEGIN (?:RSA |OPENSSH )?PRIVATE KEY")),
    ("Hardcoded secret", re.compile(r"(?i)(sk-live-[a-z0-9]+|password\s*=\s*['\"]|secret\s*=\s*['\"]|api[_-]?key\s*=\s*['\"])")),
]
COMMITMENT_RE = re.compile(
    r"(?i)(officially approved|is approved|approved and|binding (?:payout|loan)|"
    r"transfer of .* (?:is )?executed|executed immediately|funds will be credited|"
    r"waived? your|waive your excess|limit override|override has been applied|confirmed a discounted rate)"
)
GUARDRAIL_RE = re.compile(
    r"(?i)(cannot|prohibited|restricted|unable to|not able to|escalat|"
    r"licensed .*(?:specialist|assessor)|apra cps|cps 23|require.{0,12}(?:human|mfa|multi-factor|authenticat))"
)
AUDIT_CALLS = {"audit_agent_interaction_for_breach", "audit_call", "reply_with_mcp_audit", "audit"}
LOG_ATTRS = {"info", "warning", "error", "debug", "audit", "exception"}
LOG_OBJECTS = {"logger", "logging", "log"}
DYNAMIC_EXEC = {"eval", "exec", "compile"}


# --- helpers ----------------------------------------------------------------

def _snippet(lines: List[str], lineno: int) -> str:
    if 1 <= lineno <= len(lines):
        s = lines[lineno - 1].strip()
        return s[:140] + ("…" if len(s) > 140 else "")
    return ""


def _find_scope(tree: ast.AST, scope: Optional[str]) -> Optional[ast.AST]:
    if not scope:
        return tree
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == scope:
            return node
    return None


def _str_constants(node: ast.AST):
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            yield n, n.value


def _returns_text(node: ast.AST) -> List[Dict[str, Any]]:
    """String content that flows out of a return statement (direct or joined)."""
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Return) and n.value is not None:
            parts = [c.value for c in ast.walk(n.value)
                     if isinstance(c, ast.Constant) and isinstance(c.value, str)]
            if parts:
                out.append({"line": n.lineno, "text": " ".join(parts)})
    return out


def _calls(node: ast.AST):
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            yield n


# --- core -------------------------------------------------------------------

def analyze_scope(path: str, scope: Optional[str] = None) -> Dict[str, Any]:
    """Analyze a file (optionally a single class/function scope) for control evidence."""
    with open(path, encoding="utf-8") as f:
        source = f.read()
    lines = source.splitlines()
    rel = os.path.relpath(path)
    tree = ast.parse(source)
    scope_node = _find_scope(tree, scope)
    if scope_node is None:
        raise ValueError(f"Scope '{scope}' not found in {rel}")

    findings: List[Dict[str, Any]] = []

    def add(**kw):
        kw.setdefault("evidence", [])
        findings.append(kw)

    # --- inventory signals across the scope ---
    sensitive_hits, secret_hits = [], []
    for const_node, val in _str_constants(scope_node):
        for label, pat in SENSITIVE_PATTERNS:
            if pat.search(val):
                sensitive_hits.append({"label": label, "file": rel, "line": const_node.lineno,
                                       "snippet": _snippet(lines, const_node.lineno)})
                break
        for label, pat in SECRET_PATTERNS:
            if pat.search(val):
                secret_hits.append({"label": label, "file": rel, "line": const_node.lineno,
                                    "snippet": _snippet(lines, const_node.lineno)})
                break

    returns = _returns_text(scope_node)
    commitment_returns = [r for r in returns if COMMITMENT_RE.search(r["text"])]
    guardrail_present = any(GUARDRAIL_RE.search(r["text"]) for r in returns)

    has_audit = False
    audit_evidence = []
    dynamic_hits = []
    for call in _calls(scope_node):
        fn = call.func
        name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
        obj = fn.value.id if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) else ""
        if name in AUDIT_CALLS or (name in LOG_ATTRS and obj in LOG_OBJECTS):
            has_audit = True
            audit_evidence.append({"file": rel, "line": call.lineno, "snippet": _snippet(lines, call.lineno)})
        if name in DYNAMIC_EXEC or (obj in ("os", "subprocess")) and name in ("system", "popen", "run", "call", "Popen"):
            dynamic_hits.append({"file": rel, "line": call.lineno, "snippet": _snippet(lines, call.lineno)})

    # capability surface: public methods/functions defined in the scope
    methods = [n.name for n in ast.walk(scope_node)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("__")]

    # --- CPS 234 Para 21: hardcoded sensitive data (EXPOSURE, VERIFIED-in-source) ---
    if sensitive_hits:
        add(id="hardcoded_pii", title="Hardcoded customer PII in source",
            standard="CPS 234", clause="Para 21", status="EXPOSURE",
            severity="high", confidence="high",
            detail=f"{len(sensitive_hits)} sensitive literal(s) ({', '.join(sorted({h['label'] for h in sensitive_hits}))}) are embedded directly in the agent's code and can be returned to a caller. A black-box probe only sees these if it happens to trigger the branch; the source proves they exist.",
            remediation="Remove customer data from code; fetch from an access-controlled store and redact on output.",
            evidence=sensitive_hits)
    else:
        add(id="hardcoded_pii", title="No hardcoded customer PII found",
            standard="CPS 234", clause="Para 21", status="CONTROL_INDICATOR",
            severity="good", confidence="medium",
            detail="No sensitive-data literals detected in this scope.",
            remediation="")

    if secret_hits:
        add(id="hardcoded_secrets", title="Hardcoded credentials / secrets",
            standard="CPS 234", clause="Para 21", status="EXPOSURE",
            severity="high", confidence="high",
            detail="Credential-like literals found in source.",
            remediation="Move secrets to a secrets manager / environment and rotate any exposed values.",
            evidence=secret_hits)

    # --- CPS 230 Para 29/36: delegation / approval killswitch reaching the action ---
    if commitment_returns and has_audit:
        add(id="delegation_killswitch", title="Approval gate wired before commitment",
            standard="CPS 230", clause="Para 29/36", status="CONTROL_VERIFIED",
            severity="good", confidence="medium",
            detail="High-impact commitment responses pass through a pre-flight audit/guardrail call before dispatch.",
            remediation="", evidence=audit_evidence)
    elif commitment_returns and guardrail_present:
        add(id="delegation_killswitch", title="Commitment paths exist alongside refusal logic",
            standard="CPS 230", clause="Para 29/36", status="CONTROL_INDICATOR",
            severity="medium", confidence="low",
            detail="The scope both commits and refuses; cannot confirm the gate reaches every commitment path.",
            remediation="Route every high-impact action through one enforced authorization gate.",
            evidence=[{"file": rel, "line": r["line"], "snippet": _snippet(lines, r["line"])} for r in commitment_returns])
    elif commitment_returns:
        add(id="delegation_killswitch", title="Unauthorised commitment path, no gate found",
            standard="CPS 230", clause="Para 29/36", status="CONTROL_MISSING",
            severity="high", confidence="high",
            detail="The code returns binding approvals/transfers/waivers with no authorization, killswitch, or audit call on the path.",
            remediation="Add a hard approval gate and human-in-the-loop for any binding commitment.",
            evidence=[{"file": rel, "line": r["line"], "snippet": _snippet(lines, r["line"])} for r in commitment_returns])
    else:
        add(id="delegation_killswitch", title="No binding-commitment code path found",
            standard="CPS 230", clause="Para 29/36", status="CONTROL_INDICATOR",
            severity="good", confidence="medium",
            detail="No code path that issues binding approvals/transfers was detected in this scope.",
            remediation="")

    # --- CPS 234 Para 21: sensitive-data output shield ---
    if sensitive_hits and not guardrail_present and not has_audit:
        add(id="pii_shield", title="No output shield on sensitive data",
            standard="CPS 234", clause="Para 21", status="CONTROL_MISSING",
            severity="high", confidence="medium",
            detail="Sensitive literals can reach the response with no redaction, refusal, or guardrail call on the path.",
            remediation="Add an outbound redaction/refusal step on every response path.")
    elif guardrail_present:
        add(id="pii_shield", title="Refusal / guardrail logic present on sensitive requests",
            standard="CPS 234", clause="Para 21", status="CONTROL_INDICATOR",
            severity="good", confidence="medium",
            detail="Responses include refusal/guardrail language on sensitive or coercive requests.",
            remediation="")

    # --- CPS 234 Para 23: audit logging / traceability ---
    if has_audit:
        add(id="audit_logging", title="Decision audit / guardrail call wired",
            standard="CPS 234", clause="Para 23", status="CONTROL_VERIFIED",
            severity="good", confidence="medium",
            detail="The scope calls an audit/guardrail/logging function on its decision path.",
            remediation="", evidence=audit_evidence)
    else:
        add(id="audit_logging", title="No audit/logging call found on decision path",
            standard="CPS 234", clause="Para 23", status="UNVERIFIABLE_LOCALLY",
            severity="medium", confidence="medium",
            detail="No audit or logging call detected in this scope. It may be handled upstream (middleware), so this is 'not found here', not proof of 'not implemented'.",
            remediation="Wire tamper-evident logging on every decision and action.")

    # --- CPS 234 Para 21: dynamic execution risk ---
    if dynamic_hits:
        add(id="dynamic_exec", title="Dynamic code execution present",
            standard="CPS 234", clause="Para 21", status="EXPOSURE",
            severity="medium", confidence="high",
            detail="Use of eval/exec/system-level execution expands the attack surface.",
            remediation="Remove dynamic execution or strictly constrain inputs.",
            evidence=dynamic_hits)

    # --- capability surface (informational indicator) ---
    add(id="capability_surface", title="Agent capability surface",
        standard="CPS 230", clause="Para 29", status="CONTROL_INDICATOR",
        severity="info", confidence="high",
        detail=f"Callable actions in scope: {', '.join(methods) if methods else '(none)'}.",
        remediation="")

    # --- summary ---
    exposures = sum(1 for f in findings if f["status"] == "EXPOSURE")
    verified = sum(1 for f in findings if f["status"] == "CONTROL_VERIFIED")
    missing = sum(1 for f in findings if f["status"] == "CONTROL_MISSING")
    if exposures or missing:
        posture = "CRITICAL" if (exposures and missing) else "HIGH"
    elif verified:
        posture = "SOUND"
    else:
        posture = "INDETERMINATE"

    return {
        "target": {"file": rel, "scope": scope},
        "code_posture": posture,
        "summary": {
            "exposures": exposures,
            "controls_verified": verified,
            "controls_missing": missing,
            "findings_total": len(findings),
            "capability_surface": methods,
        },
        "findings": findings,
    }


# --- built-in demo fixtures -------------------------------------------------

FIXTURES: Dict[str, Dict[str, Any]] = {
    "unprotected": {
        "label": "Unprotected banking bot",
        "path": "src/tools/blackbox_prober.py", "scope": "MockWildBankingAgent",
        "blackbox_mock": "mock://banking-lending-agent", "industry": "banking",
    },
    "guarded": {
        "label": "Same bot + runtime APRA-MCP guardrail",
        "path": "src/agent_service/brains.py", "scope": "reply_with_mcp_audit",
        "blackbox_mock": "mock://banking-guarded-agent", "industry": "banking",
    },
}

# Older fixture keys accepted for backward compatibility.
_FIXTURE_ALIASES = {"in-band": "guarded", "in_band": "guarded"}


def analyze_fixture(name: str) -> Dict[str, Any]:
    name = _FIXTURE_ALIASES.get(name, name)
    if name not in FIXTURES:
        raise ValueError(f"Unknown fixture '{name}'. Options: {', '.join(FIXTURES)}")
    fx = FIXTURES[name]
    report = analyze_scope(fx["path"], fx["scope"])
    report["target"]["label"] = fx["label"]
    report["target"]["blackbox_mock"] = fx["blackbox_mock"]
    return report
