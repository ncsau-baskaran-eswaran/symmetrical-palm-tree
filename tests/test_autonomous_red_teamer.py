"""Unit tests for the Autonomous MCP-Powered Red-Teaming Agent (Codex Co-Design)."""

import pytest
from src.tools.autonomous_red_teamer import (
    AutonomousMCPRedTeamer,
    EvidenceRecorder,
    validate_target_url,
    run_autonomous_mcp_red_team_campaign,
)


@pytest.mark.anyio
async def test_autonomous_mcp_red_teamer_wild_banking_full_ladder():
    campaign = await run_autonomous_mcp_red_team_campaign(
        target_url="mock://banking-lending-agent",
        industry="banking",
        agent_role="lending_agent",
        turns=4
    )

    assert campaign["industry"] == "banking"
    assert campaign["campaign_summary"]["total_turns_executed"] == 4
    assert campaign["campaign_summary"]["ladder_depth"] == 4
    assert len(campaign["mcp_tool_execution_trace"]) >= 5

    # Verify that the prober actually invoked MCP tools
    tools_called = [call["tool_name"] for call in campaign["mcp_tool_execution_trace"]]
    assert "get_critical_operations" in tools_called
    assert "search_regulations" in tools_called
    assert "lookup_clause" in tools_called
    assert "audit_agent_for_regulatory_breach" in tools_called

    # Wild agent fails multiple rungs
    assert campaign["campaign_summary"]["total_statutory_violations"] >= 2
    assert campaign["campaign_summary"]["mandatory_apra_notifications"] >= 1
    assert campaign["campaign_summary"]["board_risk_rating"] == "CRITICAL"

    # Verify SHA-256 Evidence Manifest
    assert campaign["evidence_manifest"]["chain_integrity_valid"] is True
    assert len(campaign["evidence_manifest"]["blocks"]) == 4
    fingerprint = campaign["campaign_summary"]["evidence_manifest_fingerprint"]
    assert len(fingerprint) == 64  # Valid SHA-256 hex string

    # Verify Dossier generated
    assert "# APRA Prudential Audit Dossier" in campaign["board_dossier_markdown"]
    assert "CPS 230 Para 19" in campaign["board_dossier_markdown"]


@pytest.mark.anyio
async def test_autonomous_mcp_red_teamer_hardened_banking():
    campaign = await run_autonomous_mcp_red_team_campaign(
        target_url="mock://hardened-bank-agent",
        industry="banking",
        agent_role="lending_agent",
        turns=4
    )

    assert campaign["campaign_summary"]["compliance_score_percentage"] == 100.0
    assert campaign["campaign_summary"]["total_statutory_violations"] == 0
    assert campaign["campaign_summary"]["mandatory_apra_notifications"] == 0
    assert campaign["campaign_summary"]["board_risk_rating"] == "LOW"
    assert campaign["evidence_manifest"]["chain_integrity_valid"] is True


@pytest.mark.anyio
async def test_autonomous_mcp_red_teamer_insurance():
    campaign = await run_autonomous_mcp_red_team_campaign(
        target_url="mock://insurance-wild-agent",
        industry="insurance",
        agent_role="claims_processing_agent",
        turns=4
    )

    assert campaign["industry"] == "insurance"
    assert len(campaign["detailed_turns"]) == 4
    tools_called = [call["tool_name"] for call in campaign["mcp_tool_execution_trace"]]
    assert "get_critical_operations" in tools_called
    assert "audit_agent_for_regulatory_breach" in tools_called
    # Rung 4 tests PDS flood coverage hallucination
    rung4 = campaign["detailed_turns"][3]
    assert "Rung 4" in rung4["rung_name"]


def test_evidence_recorder_integrity_and_tampering():
    recorder = EvidenceRecorder()
    recorder.record_turn(1, "Rung 1", "prompt 1", "response 1", "PASSED", 12.5)
    recorder.record_turn(2, "Rung 2", "prompt 2", "response 2", "FAILED", 15.0)

    assert recorder.verify_chain_integrity() is True
    fp1 = recorder.get_manifest_fingerprint()
    assert len(fp1) == 64

    # Simulate adversarial tampering with block 1 response hash
    recorder.blocks[0]["response_sha256"] = "tampered_fake_hash_0000000000000000000000000000"
    assert recorder.verify_chain_integrity() is False

    # Reset and test tampering with rung_name or latency
    recorder.blocks[0]["response_sha256"] = recorder.blocks[0]["prompt_sha256"]  # reset to invalid
    recorder2 = EvidenceRecorder()
    recorder2.record_turn(1, "Rung 1: Baseline", "p1", "r1", "PASSED", 20.0)
    assert recorder2.verify_chain_integrity() is True
    recorder2.blocks[0]["rung_name"] = "Tampered Rung Name"
    assert recorder2.verify_chain_integrity() is False


def test_ssrf_protection_guardrails():
    # Allowlisted mock
    validate_target_url("mock://banking-lending-agent")

    # Disallow cloud metadata
    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_target_url("http://169.254.169.254/latest/meta-data/")

    # Disallow localhost / loopback
    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_target_url("http://localhost:8080/v1/chat")

    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_target_url("http://127.0.0.1:5000")

    # Disallow private IPs
    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_target_url("http://10.0.0.1/admin")

    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_target_url("http://192.168.1.100/api")

    # Disallow invalid scheme
    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_target_url("ftp://ftp.bank.com/data")


# --- transport failure handling (regression: unreachable target must not PASS) ---

import pytest
from src.tools import autonomous_red_teamer as _art


@pytest.mark.anyio
async def test_unreachable_target_is_not_scored_as_pass(monkeypatch):
    async def fake_probe(*args, **kwargs):
        return {
            "success": False,
            "response_text": "Connection Error: [Errno 8] nodename nor servname provided, or not known",
            "latency_ms": 12.0,
            "status_code": 0,
            "target": kwargs.get("target_url", ""),
        }

    monkeypatch.setattr(_art, "execute_probe_against_target", fake_probe)

    result = await _art.run_autonomous_mcp_red_team_campaign(
        target_url="http://unreachable.invalid/chat", industry="banking", turns=4,
    )
    s = result["campaign_summary"]
    assert s["board_risk_rating"] == "UNREACHABLE"
    assert s["compliance_score_percentage"] is None
    assert s["target_reachable"] is False
    assert s["passed_turns"] == 0
    assert s["assessed_turns"] == 0
    # short-circuits after the first failed probe; the one turn is an ERROR, never PASSED
    verdicts = [t["audit_verdict"] for t in result["detailed_turns"]]
    assert verdicts == ["ERROR"]
