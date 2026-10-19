"""Registry seeding, multi-instrument lookup, dated reporting clocks, claim timeframes, coverage and triage."""

from datetime import date

import src.db as db
from src.tools.claims_timeframes import check_claim_timeframe
from src.tools.coverage import get_coverage_map, get_obligations_for_agent, map_finding_to_obligations, triage_customer_message
from src.tools.lookup import list_instruments, lookup_specific_clause
from src.tools.notifications import add_business_days, assess_regulatory_obligations, national_public_holidays


def test_registry_rebuilds_when_corpus_changes(tmp_path, monkeypatch):
    data = tmp_path / "data"
    (data / "instruments" / "x").mkdir(parents=True)
    inst = data / "instruments" / "x" / "demo.json"
    inst.write_text('{"code": "DEMO 1", "title": "Demo", "clauses": [{"id": "D-1", "clause_number": "1", "text": "first"}]}')
    monkeypatch.setattr(db, "DATA_DIR", data)
    monkeypatch.setattr(db, "INSTRUMENTS_DIR", data / "instruments")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")

    db.init_db()
    assert db.get_clause_by_number("DEMO 1", "1")["text"] == "first"
    inst.write_text('{"code": "DEMO 1", "title": "Demo", "clauses": [{"id": "D-1", "clause_number": "1", "text": "second"}]}')
    db.init_db()
    assert db.get_clause_by_number("DEMO 1", "1")["text"] == "second"


def test_non_apra_instruments_are_searchable_and_citable():
    regulators = {i["regulator"] for i in list_instruments()["instruments"]}
    assert {"APRA", "ACCC"} <= regulators
    assert any("Code" in r for r in regulators)
    clause = lookup_specific_clause("GI Code", "claim_decision_timeframe")
    assert "error" not in clause and clause["anchor"] == "claim_decision_timeframe"
    assert "error" not in lookup_specific_clause("Life Code", "genetic_testing")
    assert "error" not in lookup_specific_clause("PHI Act 2007", "medicare_covered_services_restriction")


def test_clause_lookup_tolerates_citation_styles():
    assert lookup_specific_clause("cps230", "para 33")["clause_number"] == "33"
    assert lookup_specific_clause("CPS 234", "35")["clause_number"] == "35"


def test_national_public_holidays_and_business_days():
    holidays = national_public_holidays(2026)
    assert date(2026, 4, 3) in holidays and date(2026, 4, 6) in holidays  # Easter 2026
    assert date(2026, 12, 28) in holidays  # Boxing Day falls on Saturday
    # Tue 22 Dec 2026 + 3 business days skips Christmas (Fri) and Boxing Day observed (Mon 28)
    assert add_business_days(date(2026, 12, 22), 3) == date(2026, 12, 29)


def test_regulatory_clocks_are_dated_and_sector_aware():
    res = assess_regulatory_obligations(
        ["apra_cps234_35", "oaic_ndb", "asic_reportable_situation"],
        sectors=["general_insurance"],
        detected_at="2026-10-19T09:00:00+11:00",
    )
    by_trigger = {o["trigger"]: o for o in res["obligations"]}
    assert by_trigger["apra_cps234_35"]["due"].startswith("2026-10-22T09:00")
    assert by_trigger["oaic_ndb"]["due"] == "2026-11-18"
    assert by_trigger["asic_reportable_situation"]["status"] == "conditional"

    phi = assess_regulatory_obligations(["asic_reportable_situation"], sectors=["private_health_insurance"])
    assert phi["obligations"] == [] and phi["not_applicable"][0]["trigger"] == "asic_reportable_situation"


def test_code_breach_clock_reads_each_code():
    res = assess_regulatory_obligations(["code_breach_report"], sectors=["general_insurance", "life_insurance"],
                                        detected_at="2026-10-19T09:00:00+11:00")
    by_code = {o["instrument"]: o for o in res["obligations"]}
    assert by_code["GI Code"]["timeframe"] == "10 business days"
    assert by_code["Life Code"]["timeframe"] == "30 business days"


def test_soci_clock_needs_entity_profile():
    off = assess_regulatory_obligations(["apra_cps234_35"])
    on = assess_regulatory_obligations(["apra_cps234_35"], entity_profile={"soci_critical_insurance_asset": True})
    assert "soci_other_cyber" not in {o["trigger"] for o in off["obligations"]}
    assert "soci_other_cyber" in {o["trigger"] for o in on["obligations"]}


def test_gi_claim_timeframes():
    res = check_claim_timeframe("general_insurance", lodged_on="2026-05-01", info_complete_on="2026-10-01", today="2026-10-19")
    checks = {c["check"]: c for c in res["checks"]}
    assert checks["Decision after all information received"]["status"] == "overdue"
    assert checks["Overall claim decision limit"]["due"] == "2026-09-01"
    assert res["overdue_count"] >= 2


def test_life_claim_timeframes_by_product():
    res = check_claim_timeframe("life_insurance", lodged_on="2026-09-01", today="2026-10-19", product="income protection")
    limit = next(c for c in res["checks"] if c["check"].startswith("Claim decision limit"))
    assert limit["due"] == "2026-11-01" and limit["status"] == "within timeframe"


def test_phi_claims_have_no_code_timetable():
    assert "error" in check_claim_timeframe("private_health_insurance", lodged_on="2026-10-01")


def test_coverage_map_is_honest():
    cov = get_coverage_map()
    assert cov["totals"]["runtime_detected"] > 0
    codes = {i["code"] for i in cov["instruments"]}
    assert {"CPS 230", "GI Code", "Life Code"} <= codes


def test_obligations_for_phi_agent_exclude_asic_regimes():
    data = get_obligations_for_agent("phi_member_agent")
    cats = {c["category"] for c in data["tested_categories"]}
    assert "PHI_MEDICARE_BENEFIT_PROMISE" in cats
    assert "HAWKING_UNSOLICITED_OFFER" not in cats


def test_map_finding_to_obligations():
    res = map_finding_to_obligations("HALLUCINATED_POLICY_COVERAGE", "general_insurance")
    assert "asic_reportable_situation" in res["reporting_triggers"]
    assert {o["instrument"] for o in res["obligations"]} >= {"ASIC Act 2001", "ICA 1984"}
    assert "error" in map_finding_to_obligations("NOT_A_CATEGORY")


def test_triage_customer_message():
    res = triage_customer_message(
        "This is a formal complaint. My ex-partner threatens me and I can't afford the excess.",
        sector="general_insurance", received_at="2026-10-19T09:00:00+11:00",
    )
    assert res["is_complaint"] and res["family_violence_signals"] and res["financial_hardship_signals"]
    assert res["clocks"]["obligations"][0]["trigger"] == "idr_complaint"
    assert res["clocks"]["obligations"][0]["acknowledge_by"] == "2026-10-20"
