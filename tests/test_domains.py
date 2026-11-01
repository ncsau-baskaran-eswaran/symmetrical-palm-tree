"""Domain packs, traceable reference answers and the superannuation example domain."""

import json

import pytest

import src.db as db
from src.tools.lookup import list_domains, list_instruments, lookup_specific_clause
from src.tools.search import execute_search

KNOWN_SECTORS = {"general_insurance", "life_insurance", "private_health_insurance", "banking", "superannuation",
                 "energy_retail", "telecommunications", "water", "public_sector", "commercial"}


def test_every_domain_pack_is_well_formed_and_backed_by_instruments():
    tagged = {s for i in db.load_instrument_files() for s in i["sectors"]}
    for d in db.load_domains():
        assert {"id", "name", "sectors", "coverage", "regulators", "scope_notes", "known_gaps"} <= d.keys(), d["id"]
        assert d["coverage"] in {"screening", "reference"}
        assert set(d["sectors"]) <= KNOWN_SECTORS and set(d["sectors"]) <= tagged, d["id"]
        assert all(r["name"] and r["role"] for r in d["regulators"])


def test_duplicate_domain_alias_fails_loudly(tmp_path, monkeypatch):
    for name in ("a", "b"):
        (tmp_path / f"{name}.json").write_text(json.dumps({"id": name, "aliases": ["shared"], "sectors": []}))
    monkeypatch.setattr(db, "DOMAINS_DIR", tmp_path)
    with pytest.raises(ValueError):
        db.load_domains()


def test_list_domains_counts_match_domain_filter():
    for d in list_domains()["domains"]:
        assert d["instrument_count"] == list_instruments(domain=d["id"])["total"]
        assert d["expert_reviewed"] is False


def test_superannuation_instruments_are_sourced_and_paraphrased():
    codes = {i["code"] for i in list_instruments(domain="super")["instruments"]}
    assert {"SIS Act 1993", "SPS 515", "SPS 530", "RG 271"} <= codes
    for inst in db.load_instrument_files():
        if inst["sectors"] == ["superannuation"]:
            assert inst["source_url"].startswith("https://www.legislation.gov.au/")
            assert inst["verified_on"] and inst["text_kind"] == "paraphrase" and inst["source_version"]


def test_search_results_carry_evidence_and_disclaimer():
    res = execute_search("best financial interests", domain="superannuation")
    assert res["supporting_evidence"] and "not legal advice" in res["disclaimer"]
    top = res["results"][0]
    assert top["standard"] == "SIS Act 1993"
    ev = top["evidence"]
    assert ev["source_url"] and ev["verified_on"] == "2026-10-27" and ev["version"].startswith("C2026C00361")
    assert ev["statement_kinds"] == {"text": "paraphrase_of_source", "notes": "editorial_summary"}
    assert ev["expert_reviewed"] is False and ev["current_status"].startswith("not established")


def test_domain_filter_excludes_other_industries():
    res = execute_search("complaint", domain="superannuation", limit=50)
    assert res["results"] and {r["standard"] for r in res["results"]} <= {"RG 271", "SIS Act 1993", "SPS 515", "SPS 530", "CPS 230", "CPS 234"}
    assert all(r["clause_number"] in {"RG 271.79", "RG 271.80"} for r in res["results"] if r["standard"] == "RG 271")


def test_empty_search_says_no_supporting_evidence():
    res = execute_search("xyzzy plover", domain="superannuation")
    assert res["supporting_evidence"] is False and res["results"] == []
    assert "does not mean no obligation exists" in res["determination"]


def test_search_limit_is_capped():
    assert execute_search("must", limit=10_000)["total_results"] <= db.MAX_SEARCH_LIMIT


def test_unknown_domain_is_rejected():
    with pytest.raises(ValueError, match="Unknown domain 'mining'. Valid: banking"):
        execute_search("fees", domain="mining")


def test_lookup_clause_cites_its_source():
    res = lookup_specific_clause("SIS Act", "52(2)(c)")
    assert res["heading"] == "Best financial interests of beneficiaries"
    assert res["evidence"]["pinpoint"] == "SIS Act 1993 52(2)(c)" and "disclaimer" in res
    assert lookup_specific_clause("RG 271", "RG 271.80")["evidence"]["version"]
