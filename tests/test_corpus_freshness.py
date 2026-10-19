"""Offline tests for scripts/check_corpus_freshness.py. HTTP is mocked; no real network is used."""

import importlib.util
import json
from datetime import date
from pathlib import Path

import httpx
import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_corpus_freshness.py"
_spec = importlib.util.spec_from_file_location("check_corpus_freshness", SCRIPT)
cf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cf)

TODAY = date(2026, 10, 19)


def _inst(code, verified="2026-10-01", notes="Checked.", url=None, regulator="ASIC", clauses=2):
    return {
        "code": code, "regulator": regulator, "status": "In Force", "enforceability": "statutory",
        "text_kind": "paraphrase", "verified_on": verified, "verification_notes": notes,
        "source_url": url if url is not None else f"https://example.test/{code}",
        "clauses": [{"id": f"{code}-{n}"} for n in range(clauses)],
    }


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    d = tmp_path / "instruments"
    (d / "asic").mkdir(parents=True)
    docs = [
        _inst("FRESH"),
        _inst("OLD", verified="2025-01-01"),
        _inst("EMPTY", verified=""),
        _inst("UNSURE", notes="Read the Act. An SME should confirm the commencement date."),
        _inst("GOOD", notes="Confirmed s13 text. Confirms the date."),
        _inst("SHARED", url="https://example.test/FRESH"),
    ]
    for doc in docs:
        (d / "asic" / f"{doc['code']}.json").write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(cf, "INSTRUMENTS_DIR", d)
    monkeypatch.setattr(cf, "LOCK_PATH", tmp_path / "sources.lock.json")
    monkeypatch.setattr(cf, "REVIEW_PATH", tmp_path / "docs" / "CORPUS_REVIEW.md")
    return d


def test_staleness_findings(corpus):
    findings = {f["code"]: f for f in cf.assess_staleness(cf.load_instruments(), 90, TODAY)}
    assert set(findings) == {"OLD", "EMPTY", "UNSURE"}
    assert findings["EMPTY"]["unverified"] and not findings["OLD"]["unverified"]
    assert "days ago" in findings["OLD"]["reasons"][0]
    assert "confirm" in findings["UNSURE"]["uncertainty_items"][0]


def test_affirmative_confirmed_is_not_a_marker():
    assert cf.uncertainty_items("Confirmed s13. The Act confirms this.") == []
    assert cf.uncertainty_items("Date was not confirmed. Fine.") == ["Date was not confirmed."]


def test_staleness_exit_codes(corpus, capsys):
    assert cf.main(["staleness"]) == 0
    assert cf.main(["staleness", "--fail-on-unverified"]) == 1
    out = capsys.readouterr().out
    assert "EMPTY" in out and "ASIC" in out


def test_review_pack_generation(corpus):
    assert cf.main(["review-pack"]) == 0
    text = cf.REVIEW_PATH.read_text(encoding="utf-8")
    assert "| EMPTY | ASIC | In Force | statutory | 2 | UNVERIFIED | paraphrase |" in text
    assert "**UNSURE**" in text and "no `verified_on`" in text
    assert "## Sign-off" in text and "Reviewer" in text
    assert "General Insurance Code" in text and "weekly" in text
    assert "—" not in text and "–" not in text


def test_unique_sources_dedupes(corpus):
    sources = cf.unique_sources(cf.load_instruments())
    assert sorted(sources["https://example.test/FRESH"]) == ["FRESH", "SHARED"]


def test_normalise_body_ignores_scripts_and_whitespace():
    a = b"<html><script>var t=1;</script><p>Hello   world</p><!-- c --></html>"
    b = b"<html><script>var t=2;</script><p>Hello world</p></html>"
    assert cf.normalise_body(a) == cf.normalise_body(b)
    assert cf.normalise_body(b"%PDF-1.7 raw") == b"%PDF-1.7 raw"


def test_extract_legislation_id():
    body = b"C2004A02944 C2004A02944 C2024C00063"
    assert cf.extract_legislation_id("https://www.legislation.gov.au/C2004A02944/latest/text", body) == "C2024C00063"
    assert cf.extract_legislation_id("https://asic.gov.au/x", body) is None


def _mock_client(pages):
    """pages: url -> (status, body) or an Exception to raise."""
    def handler(request: httpx.Request) -> httpx.Response:
        page = pages[str(request.url)]
        if isinstance(page, Exception):
            raise page
        return httpx.Response(page[0], content=page[1], headers={"etag": "abc"})
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_snapshot_then_diff(corpus, monkeypatch, capsys):
    pages = {
        "https://example.test/FRESH": (200, b"<p>one</p>"),
        "https://example.test/OLD": (200, b"<p>two</p>"),
        "https://example.test/EMPTY": (403, b"blocked"),
        "https://example.test/UNSURE": httpx.ConnectError("boom"),
        "https://example.test/GOOD": (200, b"<p>five</p>"),
    }
    monkeypatch.setattr(cf, "make_client", lambda: _mock_client(pages))
    assert cf.main(["snapshot"]) == 0
    assert "3 of 5 sources reachable" in capsys.readouterr().out
    lock = json.loads(cf.LOCK_PATH.read_text(encoding="utf-8"))["sources"]
    fresh = lock["https://example.test/FRESH"]
    assert fresh["etag"] == "abc" and sorted(fresh["instruments"]) == ["FRESH", "SHARED"]
    assert lock["https://example.test/EMPTY"]["status"] == 403 and not lock["https://example.test/EMPTY"]["reachable"]
    assert "ConnectError" in lock["https://example.test/UNSURE"]["error"]

    # Unchanged corpus: exit 0, unreachable sources reported but not treated as change.
    assert cf.main(["diff"]) == 0
    out = capsys.readouterr().out
    assert "changed=0 unreachable=2 unchanged=3" in out

    # One page changes: exit 2.
    pages["https://example.test/OLD"] = (200, b"<p>two, amended</p>")
    assert cf.main(["diff"]) == cf.EXIT_CHANGED
    assert "CHANGED https://example.test/OLD" in capsys.readouterr().out


def test_diff_without_lock(corpus, capsys):
    assert cf.main(["diff"]) == 1
