"""Toolset and sector scoping: the default surface stays lean, opt-in groups add tools, legacy names survive."""

import asyncio
import importlib

import pytest

import src.config as config


def _load_server(monkeypatch, toolsets=None, sectors=None):
    for key, value in (("GUARDIAN_TOOLSETS", toolsets), ("GUARDIAN_SECTORS", sectors)):
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    import src.server as server
    return importlib.reload(server)


def _names(server):
    tools = asyncio.run(server.mcp.list_tools())
    prompts = asyncio.run(server.mcp.list_prompts())
    return {t.name for t in tools}, {p.name for p in prompts}


@pytest.fixture(autouse=True)
def _restore(monkeypatch):
    yield
    monkeypatch.delenv("GUARDIAN_TOOLSETS", raising=False)
    monkeypatch.delenv("GUARDIAN_SECTORS", raising=False)
    import src.server as server
    importlib.reload(server)


CORE = {
    "audit_agent_for_regulatory_breach", "triage_customer_message", "check_claim_timeframe",
    "assess_regulatory_obligations", "map_finding_to_obligations", "get_obligations", "get_coverage_map",
}
REFERENCE = {"list_instruments", "lookup_clause", "search_regulations", "lookup_definition"}


def test_default_surface_is_core_and_reference(monkeypatch):
    tools, prompts = _names(_load_server(monkeypatch))
    assert tools == CORE | REFERENCE
    assert "simulate_agent_red_team_audit" not in tools
    assert "life_claim_conduct_review" in prompts and "phi_member_conversation_audit" in prompts


def test_opt_in_toolsets_add_their_tools(monkeypatch):
    tools, _ = _names(_load_server(monkeypatch, toolsets="core,redteam,governance"))
    assert {"probe_external_agent", "run_autonomous_red_team_probe", "get_insurance_red_team_test_cases"} <= tools
    assert {"get_cps230_requirements", "analyze_agent_code", "check_agent_architecture_compliance"} <= tools
    assert not REFERENCE & tools


def test_all_restores_every_legacy_name(monkeypatch):
    tools, _ = _names(_load_server(monkeypatch, toolsets="all"))
    legacy = {
        "list_supported_standards", "get_standard_summary", "assess_incident_notification", "get_critical_operations",
        "get_material_service_providers", "get_contract_requirements", "get_standards_interaction",
        "get_sector_adversarial_test_suite", "probe_external_agent_for_apra_breaches", "run_autonomous_mcp_red_team_probe",
    }
    assert legacy <= tools
    assert len(tools) == 29


def test_unknown_toolset_fails_loudly():
    with pytest.raises(ValueError):
        config.enabled_toolsets("core,nonsense")


def test_phi_scope_hides_gi_and_life_prompts(monkeypatch):
    server = _load_server(monkeypatch, sectors="phi")
    _, prompts = _names(server)
    assert prompts == {"phi_member_conversation_audit"}
    listed = server.list_instruments()
    assert listed["sector_scope"] == ["private_health_insurance"]
    assert all("private_health_insurance" in i["sectors"] for i in listed["instruments"])


def test_scope_narrows_inferred_audit_sectors(monkeypatch):
    _load_server(monkeypatch, sectors="life")
    from src.tools.agent_auditor import audit_agent_interaction_for_breach as audit
    res = audit("customer_service", "Approve my claim now", "I've approved your claim for $20,000.")
    assert res["sectors_evaluated"] == ["life_insurance"]
    explicit = audit("customer_service", "Is flood covered?", "Yes, you're fully covered for flood damage.", sector="general_insurance")
    assert explicit["sectors_evaluated"] == ["general_insurance"]


def test_merged_reporting_tool_includes_apra_decision(monkeypatch):
    server = _load_server(monkeypatch)
    res = server.assess_regulatory_obligations(
        incident_type="Agent leaked member records", is_cyber_or_infosec=True, is_material_impact=True,
        detected_at="2026-10-19T09:00:00+11:00",
    )
    assert res["apra_assessment"]["deduplication_rule_active"] is True
    assert {"apra_cps234_35", "oaic_ndb"} <= {o["trigger"] for o in res["obligations"]}


def test_cps230_requirements_merge(monkeypatch):
    server = _load_server(monkeypatch, toolsets="governance")
    res = server.get_cps230_requirements("general_insurance")
    assert "Claims processing" in res["critical_operations"]["mandatory_sector_critical_operations"]
    assert {"material_service_providers", "contracts", "cps234_interaction"} <= set(res)
