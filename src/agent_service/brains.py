"""Agent behavior adapters for the standalone financial-services service."""

from typing import Any, Callable, Dict

from src.tools.blackbox_prober import MockHardenedBankingAgent, MockWildBankingAgent
from src.simulation.agent import HypotheticalClaimsAgent

SECTORS = ("banking", "insurance")
MODES = ("vulnerable", "hardened", "guarded")

# Older names for the runtime-guardrail mode, accepted for backward compatibility.
_GUARDED_ALIASES = ("guarded", "in_band", "in_band_guardrail", "mcp_in_band")

_SECTOR_ROLE = {
    "banking": "lending_agent",
    "insurance": "claims_processing_agent",
}


class Brain:
    """Agent draft behavior plus optional metadata for MCP pre-flight auditing."""

    def __init__(
        self,
        name: str,
        fn: Callable[[str], str],
        *,
        audit_role: str | None = None,
        audit_context: Dict[str, Any] | None = None,
    ):
        self.name = name
        self._fn = fn
        self.audit_role = audit_role
        self.audit_context = audit_context or {}

    def reply(self, prompt: str) -> str:
        if self.audit_role:
            raise RuntimeError("Guarded brains require reply_with_mcp_audit()")
        return self._fn(prompt)

    async def reply_with_mcp_audit(self, prompt: str, audit_call: Callable[..., Any]) -> str:
        """Draft locally, then ask the MCP tool before returning any candidate reply."""
        if not self.audit_role:
            return self._fn(prompt)

        draft = self._fn(prompt)
        audit = await audit_call(
            agent_role=self.audit_role,
            user_prompt=prompt,
            agent_response=draft,
            context=self.audit_context,
        )
        verdict = audit.get("audit_verdict")
        if verdict == "PASSED":
            return draft
        if verdict != "FAILED":
            raise RuntimeError("MCP audit returned an unknown verdict")

        from src.tools.agent_auditor import guardrail_citations, guardrail_fallback_text

        cites = guardrail_citations(audit)
        reason = f" ({cites})" if cites else ""
        return (
            f"[APRA MCP RUNTIME PRE-FLIGHT GUARDRAIL] Candidate reply was withheld before dispatch{reason}; "
            f"no action has been taken on it. {guardrail_fallback_text(audit)}"
        )


def get_brain(sector: str, mode: str) -> Brain:
    """Resolve a startup-fixed (sector, mode) pair to its agent draft behavior."""
    sector = (sector or "").lower().strip()
    mode = (mode or "").lower().strip()
    if mode in _GUARDED_ALIASES:
        mode = "guarded"
    if sector not in SECTORS:
        raise ValueError(f"Unknown sector '{sector}'. Expected one of {SECTORS}.")
    if mode not in MODES:
        raise ValueError(f"Unknown mode '{mode}'. Expected one of {MODES}.")

    if sector == "banking":
        if mode == "vulnerable":
            return Brain("banking/vulnerable", MockWildBankingAgent().process)
        if mode == "hardened":
            return Brain("banking/hardened", MockHardenedBankingAgent().process)
        return Brain(
            "banking/guarded",
            MockWildBankingAgent().process,
            audit_role=_SECTOR_ROLE["banking"],
        )

    if mode == "vulnerable":
        return Brain("insurance/vulnerable", HypotheticalClaimsAgent("vulnerable").process_message)
    if mode == "hardened":
        return Brain("insurance/hardened", HypotheticalClaimsAgent("hardened").process_message)
    return Brain(
        "insurance/guarded",
        HypotheticalClaimsAgent("vulnerable").process_message,
        audit_role=_SECTOR_ROLE["insurance"],
        audit_context={"claim_amount": 85000},
    )
