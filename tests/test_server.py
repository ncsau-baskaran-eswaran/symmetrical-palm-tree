"""Comprehensive test suite for APRA Regulations MCP Server."""

import pytest
from src.tools.lookup import list_standards, get_standard_overview, lookup_specific_clause
from src.tools.search import execute_search
from src.tools.notifications import assess_notification_requirements, list_all_notification_rules
from src.tools.operations import (
    get_mandatory_critical_operations,
    get_mandatory_material_service_providers,
    get_service_provider_contract_checklist,
)
from src.tools.interactions import get_cps230_cps234_interaction_analysis
from src.server import (
    get_cps230_resource,
    get_cps234_resource,
    get_notification_matrix_resource,
)


def test_list_standards():
    standards = list_standards()
    assert len(standards) >= 2
    codes = [s["code"] for s in standards]
    assert "CPS 230" in codes
    assert "CPS 234" in codes


def test_standard_overview():
    std_230 = get_standard_overview("CPS 230")
    assert std_230["code"] == "CPS 230"
    assert "F2026L00475" in std_230["legislative_instrument"]
    assert "banking" in std_230["sectors"]

    std_234 = get_standard_overview("CPS 234")
    assert std_234["code"] == "CPS 234"
    assert "F2018L01745" in std_234["legislative_instrument"]


def test_lookup_specific_clauses():
    # CPS 230 para 32: 72 hour notification
    p33 = lookup_specific_clause("CPS 230", "32")
    assert "72 hours" in p33["statutory_text"]
    assert p33["notification_trigger"] == "72_hours"

    # CPS 230 para 41: 24 hour notification for disruption outside tolerance
    p42 = lookup_specific_clause("CPS 230", "41")
    assert "24 hours" in p42["statutory_text"]
    assert p42["notification_trigger"] == "24_hours"

    # CPS 234 para 35: 72 hour notification for info sec incidents
    p35 = lookup_specific_clause("CPS 234", "35")
    assert "72 hours" in p35["statutory_text"]
    assert p35["notification_trigger"] == "72_hours"

    # CPS 234 para 13: Board ultimate responsibility
    p13 = lookup_specific_clause("CPS 234", "13")
    assert "ultimately responsible" in p13["statutory_text"]


def test_search_regulations():
    # Search for tolerance
    res_tol = execute_search("tolerance levels")
    assert res_tol["total_results"] > 0
    assert any("CPS 230" in r["standard"] for r in res_tol["results"])

    # Search for cyber incident in CPS 234
    res_cyber = execute_search("incident", standard_code="CPS 234")
    assert res_cyber["total_results"] > 0
    for r in res_cyber["results"]:
        assert r["standard"] == "CPS 234"


def test_notification_decision_tree():
    # Scenario 1: Critical outage exceeding tolerance -> 24h
    res_24h = assess_notification_requirements(
        incident_type="Core payments outage exceeding 4hr tolerance",
        is_cyber_or_infosec=False,
        exceeds_tolerance=True
    )
    timeframes = [o["timeframe"] for o in res_24h["applicable_statutory_obligations"]]
    assert "24 hours" in timeframes
    assert any("CRITICAL" in o["urgency"] for o in res_24h["applicable_statutory_obligations"])

    # Scenario 2: Cyber attack reported under CPS 234 -> triggers 72h & de-duplication safe harbor
    res_cyber = assess_notification_requirements(
        incident_type="Ransomware breach of customer database",
        is_cyber_or_infosec=True,
        exceeds_tolerance=False,
        is_material_impact=True
    )
    assert res_cyber["deduplication_rule_active"] is True
    timeframes = [o["timeframe"] for o in res_cyber["applicable_statutory_obligations"]]
    assert "72 hours" in timeframes
    assert any("Footnote 11" in note for note in res_cyber["advisory_notes"])

    # Scenario 3: Unremediated control weakness -> 10 business days
    res_weakness = assess_notification_requirements(
        incident_type="Penetration test critical auth bypass cannot be patched for 60 days",
        is_control_weakness=True
    )
    timeframes = [o["timeframe"] for o in res_weakness["applicable_statutory_obligations"]]
    assert "10 business days" in timeframes


def test_mandatory_critical_operations():
    # Banking / ADI
    adi_ops = get_mandatory_critical_operations("banking")
    assert "Payments" in adi_ops["mandatory_sector_critical_operations"]
    assert "Settlements and clearing" in adi_ops["mandatory_sector_critical_operations"]

    # Insurance
    ins_ops = get_mandatory_critical_operations("general_insurance")
    assert "Claims processing" in ins_ops["mandatory_sector_critical_operations"]


def test_material_service_providers():
    adi_msps = get_mandatory_material_service_providers("banking")
    assert "Credit assessment" in adi_msps["mandatory_sector_msps"]
    assert "Core technology services" in adi_msps["mandatory_cross_entity_msps"][1]

    ins_msps = get_mandatory_material_service_providers("insurance")
    assert "Underwriting" in ins_msps["mandatory_sector_msps"]
    assert "Reinsurance" in ins_msps["mandatory_sector_msps"]


def test_contract_checklist_and_exemptions():
    checklist = get_service_provider_contract_checklist()
    clauses = checklist["mandatory_contract_clauses"]
    assert any("audit access" in c.lower() for c in clauses)
    assert any("apra" in c.lower() for c in clauses)
    assert any("sub-contractor" in c.lower() for c in clauses)

    exemptions = checklist["exempt_provider_categories_attachment"]
    assert "Central banks (Reserve Bank of Australia)" in exemptions
    assert "Financial messaging infrastructures (SWIFT, SuperStream gateways)" in exemptions


def test_cps230_cps234_interactions():
    analysis = get_cps230_cps234_interaction_analysis()
    assert len(analysis["key_intersections"]) >= 4
    domains = [k["domain"] for k in analysis["key_intersections"]]
    assert "Technology & Cyber Risk" in domains
    assert "Incident Reporting & De-duplication" in domains


def test_mcp_resources():
    res_230 = get_cps230_resource()
    assert "CPS 230 Operational Risk Management" in res_230
    assert "Paragraph 42" in res_230 or "[42]" in res_230

    res_234 = get_cps234_resource()
    assert "CPS 234 Information Security" in res_234
    assert "[35]" in res_234

    matrix = get_notification_matrix_resource()
    assert "24 hours" in matrix
    assert "72 hours" in matrix
