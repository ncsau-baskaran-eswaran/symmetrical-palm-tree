"""Red-team packs: every cited obligation resolves, scenarios point at real categories, and the audit and judge use them."""

import json

import pytest

import src.db as db
from src.rules import judge, packs
from src.rules.audit import resolve_sectors
from src.tools.agent_auditor import audit_agent_interaction_for_breach, get_unified_adversarial_suite, pack_scenarios

PACKS = packs.load_packs()


@pytest.mark.parametrize("pack", PACKS, ids=[p["id"] for p in PACKS])
def test_pack_citations_resolve_and_scenarios_match(pack):
    ids = [c["id"] for c in pack["categories"]]
    assert len(ids) == len(set(ids)) and pack["categories"]
    for cat in pack["categories"]:
        assert cat["severity"] in {"CRITICAL", "HIGH", "MEDIUM"} and cat["description"]
        assert cat["obligations"], cat["id"]
        for ob in cat["obligations"]:
            assert db.get_clause_by_number(ob["code"], ob["clause"]), (cat["id"], ob)
    for sc in pack["scenarios"]:
        assert sc["category"] in ids, sc["id"]
        assert sc["adversarial_prompt"] and sc["breach_condition"]


def test_every_pack_sector_has_a_domain_pack_and_instruments():
    domains = {s for d in db.load_domains() for s in d["sectors"]}
    tagged = {s for i in db.load_instrument_files() for s in i["sectors"]}
    assert packs.pack_sectors() <= domains and packs.pack_sectors() <= tagged


def test_sector_resolution_for_new_industries():
    assert resolve_sectors("", "telco") == frozenset({"telecommunications"})
    assert resolve_sectors("energy_retail_agent") == frozenset({"energy_retail"})
    assert resolve_sectors("government_services_agent") == frozenset({"public_sector"})
    # Insurance roles keep their sector even when they contain a new-industry word.
    assert resolve_sectors("water_damage_claims_agent") == frozenset({"general_insurance"})


def test_new_industry_without_judge_is_not_screened():
    res = audit_agent_interaction_for_breach("telco_support_agent", "My bill is wrong", "Sure, I've cut your service.",
                                             context={"judge": False}, sector="telecommunications")
    assert res["audit_verdict"] == "INCONCLUSIVE" and res["screen_result"] == "NOT_SCREENED"
    assert "CPS 230" not in res["governance_advisory"]


def test_judge_uses_pack_categories_and_cites_pack_obligations():
    captured = {}

    def fake(prompt):
        captured["prompt"] = prompt
        return json.dumps({"findings": [{"category": "HARDSHIP_DISCONNECTION_THREAT", "evidence_span": "disconnect you tomorrow",
                                         "confidence": 0.9, "reason": "Threatens disconnection after hardship was raised."}]})

    judge.set_judge(fake)
    try:
        res = audit_agent_interaction_for_breach(
            "telco_support_agent", "I lost my job and can't pay this month.",
            "If you don't pay we will disconnect you tomorrow.", sector="telecommunications")
    finally:
        judge.set_judge(None)
    assert "telecommunications consumer protection compliance reviewer" in captured["prompt"]
    assert "HARDSHIP_DISCONNECTION_THREAT" in captured["prompt"] and "CLAIM_TIMEFRAME_MISSTATEMENT" not in captured["prompt"]
    flag = next(f for f in res["review_flags"] if f["category"] == "HARDSHIP_DISCONNECTION_THREAT")
    assert flag["citations"] and all(o["resolved"] for o in flag["obligations"])
    assert res["screen_result"] == "REVIEW"


def test_insurance_judge_prompt_is_unchanged():
    prompt = judge.build_prompt("claims_processing_agent", "q", "a", frozenset({"general_insurance"}), {"X": "y"})
    assert prompt.startswith("You are an Australian insurance compliance reviewer.")


def test_red_team_suite_for_each_industry():
    for industry in ("superannuation", "energy_retail", "telecommunications", "water", "public_sector", "commercial"):
        suite = get_unified_adversarial_suite(industry=industry)
        assert suite and all(tc["pack"] and tc["adversarial_prompt"] for tc in suite), industry
    assert {tc["pack"] for tc in pack_scenarios("superannuation")} == {"superannuation", "baseline"}
    banking = get_unified_adversarial_suite(industry="banking")
    assert any(tc.get("pack") == "banking" for tc in banking) and any(not tc.get("pack") for tc in banking)


def test_judge_provider_model_notation(monkeypatch):
    monkeypatch.setenv("GUARDIAN_JUDGE_PROVIDER", "azure_ai/gpt-5-6-sol")
    assert judge.effective_judge({}) == {"provider": "azure_ai", "model": "gpt-5-6-sol"}
    monkeypatch.setenv("GUARDIAN_JUDGE_PROVIDER", " Azure_AI / gpt-5-6-sol ")
    assert judge.effective_judge({}) == {"provider": "azure_ai", "model": "gpt-5-6-sol"}
