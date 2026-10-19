"""Corpus freshness monitoring and expert review pack for the regulatory instrument corpus.

    .venv/bin/python scripts/check_corpus_freshness.py staleness [--max-age-days 90] [--fail-on-unverified]
    .venv/bin/python scripts/check_corpus_freshness.py snapshot      # online, writes src/data/sources.lock.json
    .venv/bin/python scripts/check_corpus_freshness.py diff          # online, exit 2 if any source changed
    .venv/bin/python scripts/check_corpus_freshness.py review-pack   # writes docs/CORPUS_REVIEW.md

`staleness` and `review-pack` are offline. `snapshot` and `diff` fetch every unique `source_url` with a polite
User-Agent, a timeout and small concurrency, and never raise on network failure (failures are recorded).
"""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

ROOT = Path(__file__).resolve().parent.parent
INSTRUMENTS_DIR = ROOT / "src" / "data" / "instruments"
LOCK_PATH = ROOT / "src" / "data" / "sources.lock.json"
REVIEW_PATH = ROOT / "docs" / "CORPUS_REVIEW.md"

USER_AGENT = "guardian-compliance-mcp-freshness-check/1.0 (polite, low-volume)"
TIMEOUT_SECONDS = 30.0
MAX_WORKERS = 4

# Phrases in verification_notes that signal something a human must still confirm.
UNCERTAINTY_MARKERS = (
    "not verified", "unverified", "not yet verified", "not re-verified", "not yet re-verified", "could not",
    "not confirmed", "confirm", "verify", "draft", "placeholder", "estimated", "not re-read", "not yet commenced",
)
# "confirm" must not match the affirmative "confirmed" or "confirms", hence the negative lookahead.
_MARKER_RE = re.compile(
    "|".join(re.escape(m) for m in UNCERTAINTY_MARKERS).replace("confirm|", "confirm(?!ed|s)|"), re.IGNORECASE
)

# Federal Register compilation ids (letter C in the middle), e.g. C2025C00148, F2026C00648. The title id (A or L)
# never changes, so it is uninformative.
_LEG_ID_RE = re.compile(r"\b[CF]\d{4}C\d{5}\b")

EXIT_CHANGED = 2


# ---------------------------------------------------------------------------------------------------------------------
# Corpus loading and staleness
# ---------------------------------------------------------------------------------------------------------------------

def load_instruments() -> List[Dict[str, Any]]:
    """Load every instrument JSON under INSTRUMENTS_DIR, sorted by regulator then code."""
    out = []
    for path in sorted(INSTRUMENTS_DIR.rglob("*.json")):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["_file"] = str(path.relative_to(INSTRUMENTS_DIR))
        out.append(data)
    return sorted(out, key=lambda d: (str(d.get("regulator", "")), str(d.get("code", ""))))


def uncertainty_items(notes: str) -> List[str]:
    """Sentences of the verification notes that contain an uncertainty marker."""
    sentences = re.split(r"(?<=[.;])\s+", (notes or "").strip())
    return [s.strip() for s in sentences if s.strip() and _MARKER_RE.search(s)]


def _parse_date(value: str) -> Optional[date]:
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return None


def assess_staleness(
    instruments: List[Dict[str, Any]], max_age_days: int = 90, today: Optional[date] = None
) -> List[Dict[str, Any]]:
    """Return one finding per instrument that needs attention, with reasons."""
    today = today or date.today()
    findings = []
    for inst in instruments:
        reasons: List[str] = []
        verified = (inst.get("verified_on") or "").strip()
        parsed = _parse_date(verified)
        if not verified:
            reasons.append("verified_on is empty")
        elif parsed is None:
            reasons.append(f"verified_on is not an ISO date: {verified!r}")
        elif (today - parsed).days > max_age_days:
            reasons.append(f"verified {(today - parsed).days} days ago (limit {max_age_days})")
        items = uncertainty_items(inst.get("verification_notes", ""))
        if items:
            reasons.append(f"{len(items)} verification note(s) flag uncertainty")
        if reasons:
            findings.append({
                "code": inst.get("code", ""),
                "regulator": inst.get("regulator", ""),
                "verified_on": verified,
                "unverified": parsed is None,
                "reasons": reasons,
                "uncertainty_items": items,
            })
    return findings


def cmd_staleness(args: argparse.Namespace) -> int:
    instruments = load_instruments()
    findings = assess_staleness(instruments, args.max_age_days)
    by_reg: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for f in findings:
        by_reg[f["regulator"]].append(f)
    print(f"{len(findings)} of {len(instruments)} instruments need attention (max age {args.max_age_days} days)")
    for reg in sorted(by_reg):
        print(f"\n{reg}")
        for f in by_reg[reg]:
            print(f"  {f['code']}: {'; '.join(f['reasons'])} (verified_on={f['verified_on'] or 'EMPTY'})")
            for item in f["uncertainty_items"]:
                print(f"      - {item}")
    unverified = [f["code"] for f in findings if f["unverified"]]
    if unverified:
        print(f"\nEmpty or invalid verified_on: {', '.join(unverified)}")
        if args.fail_on_unverified:
            return 1
    return 0


# ---------------------------------------------------------------------------------------------------------------------
# Source fetching: snapshot and diff
# ---------------------------------------------------------------------------------------------------------------------

def unique_sources(instruments: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Map each unique source_url to the instrument codes that cite it."""
    sources: Dict[str, List[str]] = defaultdict(list)
    for inst in instruments:
        url = (inst.get("source_url") or "").strip()
        if url:
            sources[url].append(inst.get("code", ""))
    return dict(sources)


def normalise_body(body: bytes) -> bytes:
    """Strip scripts, styles, comments, tags and whitespace so cosmetic page churn does not change the hash.

    Non-text bodies (PDFs) are returned unchanged.
    """
    if body[:5] == b"%PDF-":
        return body
    text = body.decode("utf-8", errors="replace")
    text = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1\s*>", " ", text)
    text = re.sub(r"(?s)<!--.*?-->", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip().encode("utf-8")


def extract_legislation_id(url: str, body: bytes) -> Optional[str]:
    """Most frequent compilation id in the page, for legislation.gov.au URLs only."""
    if "legislation.gov.au" not in url:
        return None
    ids = _LEG_ID_RE.findall(body.decode("utf-8", errors="replace"))
    return Counter(ids).most_common(1)[0][0] if ids else None


def make_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf,*/*;q=0.8"},
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
    )


def fetch_source(client: httpx.Client, url: str) -> Dict[str, Any]:
    """Fetch one URL and return its snapshot record. Network errors are recorded, never raised."""
    try:
        resp = client.get(url)
    except httpx.HTTPError as exc:
        return {"reachable": False, "error": f"{type(exc).__name__}: {exc}"[:300]}
    body = resp.content
    return {
        "reachable": resp.status_code < 400,
        "status": resp.status_code,
        "final_url": str(resp.url),
        "content_length": len(body),
        "sha256": hashlib.sha256(normalise_body(body)).hexdigest(),
        "etag": resp.headers.get("etag"),
        "last_modified": resp.headers.get("last-modified"),
        "legislation_id": extract_legislation_id(url, body),
    }


def fetch_all(urls: List[str]) -> Dict[str, Dict[str, Any]]:
    with make_client() as client:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            results = list(pool.map(lambda u: fetch_source(client, u), urls))
    return dict(zip(urls, results))


def cmd_snapshot(_: argparse.Namespace) -> int:
    sources = unique_sources(load_instruments())
    fetched = fetch_all(sorted(sources))
    lock = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user_agent": USER_AGENT,
        "sources": {u: {**fetched[u], "instruments": sorted(sources[u])} for u in sorted(sources)},
    }
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ok = [u for u, r in fetched.items() if r["reachable"]]
    bad = {u: r for u, r in fetched.items() if not r["reachable"]}
    print(f"{len(ok)} of {len(fetched)} sources reachable; lock written to {LOCK_PATH}")
    for u, r in bad.items():
        print(f"  blocked/unreachable: {u} ({r.get('status') or r.get('error')})")
    return 0


def compare_record(old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
    """Describe differences between a locked record and a fresh fetch (empty list means unchanged)."""
    diffs = []
    for key in ("sha256", "legislation_id", "final_url"):
        if old.get(key) != new.get(key):
            diffs.append(f"{key}: {old.get(key)} -> {new.get(key)}")
    return diffs


def diff_against_lock(lock: Dict[str, Any], fetched: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Classify each locked source as changed, unreachable or unchanged."""
    changed: Dict[str, List[str]] = {}
    unreachable: Dict[str, str] = {}
    unchanged: List[str] = []
    for url, old in lock.get("sources", {}).items():
        new = fetched.get(url, {"reachable": False, "error": "not fetched"})
        if not new.get("reachable"):
            unreachable[url] = str(new.get("status") or new.get("error"))
        elif not old.get("reachable"):
            changed[url] = ["previously unreachable, now reachable"]
        elif diffs := compare_record(old, new):
            changed[url] = diffs
        else:
            unchanged.append(url)
    return {"changed": changed, "unreachable": unreachable, "unchanged": unchanged}


def cmd_diff(_: argparse.Namespace) -> int:
    if not LOCK_PATH.exists():
        print(f"No lock file at {LOCK_PATH}; run `snapshot` first.", file=sys.stderr)
        return 1
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    report = diff_against_lock(lock, fetch_all(sorted(lock.get("sources", {}))))
    print(f"changed={len(report['changed'])} unreachable={len(report['unreachable'])} "
          f"unchanged={len(report['unchanged'])} (lock from {lock.get('generated_at')})")
    for url, diffs in report["changed"].items():
        cited = ", ".join(lock["sources"][url].get("instruments", []))
        print(f"  CHANGED {url} [{cited}]")
        for d in diffs:
            print(f"      {d}")
    for url, why in report["unreachable"].items():
        print(f"  UNREACHABLE {url}: {why}")
    return EXIT_CHANGED if report["changed"] else 0


# ---------------------------------------------------------------------------------------------------------------------
# Expert review pack
# ---------------------------------------------------------------------------------------------------------------------

REVIEW_INTRO = """\
# Corpus expert review pack

This corpus was paraphrased by AI research agents from public sources. **It has not been signed off by a compliance
or legal expert.** Treat every entry as a research aid until the sign-off table at the end is completed. Do not edit
instrument JSON to "fix" an entry without recording the change in that instrument's `verification_notes` and
updating `verified_on`.

This file is generated by `scripts/check_corpus_freshness.py review-pack`; edit the generator, not the output.
Regenerate it after any corpus change, and refresh `src/data/sources.lock.json` with `snapshot` once a reviewer
has accepted the current state of the sources.

Generated on {today}. {count} instruments, {clauses} clauses.

## Known open items

| Item | Why it needs a human |
| --- | --- |
| ACL (Competition and Consumer Act 2010 Sch 2) | File authored without verification and with no `verified_on`. Section numbers and the exclusion of private health insurance are unchecked. |
| CPS 230 | Condensed (30 entries) and carried over from the original corpus, not re-verified against the registered instrument. |
| CPS 234 | Carried over from the original corpus, not re-verified against the registered instrument. |
| General Insurance Code | Redraft is due to be lodged with ASIC in late October 2026. The corpus holds the 2020 Code (2021 update); clause numbers and obligations may change. |
| Life Insurance Code | Clause renumbering between versions; confirm every cited clause number against the March 2025 Code. |
| PHI Complying Product Rules | Confirm the compilation date and number against the Federal Register. |
| Ransomware payment reporting (Cyber Security Act 2024) | Commencement is recorded as 29 or 30 May 2025 in different places; confirm which is correct. |
| SOCI Act asset thresholds | Confirm thresholds for insurance assets and which insurers are in scope. |
| FAR enhanced notification thresholds | Confirm the thresholds for enhanced notification under the Financial Accountability Regime. |
| Genetic testing ASIC consent form | Confirm whether the ASIC consent form is approved and in use. |

## Reviewer checklist

Apply to each instrument you are signing off:

- [ ] Accuracy of paraphrase: each clause states the obligation faithfully, with no added or dropped conditions.
- [ ] Section and paragraph numbers: `clause_number` resolves to the right provision in the cited source.
- [ ] Commencement and effective dates: `effective_date`, `amended_date` and `status` are correct as at today.
- [ ] Sector applicability: `sectors`, `entity_types` and per-clause `sectors` match who is actually bound.
- [ ] Enforceability: statutory, prudential, contractual code or guidance is labelled correctly.
- [ ] Anchors used by detection rules: every `(code, clause_number)` referenced from `src/tools` rules is the right
      citation for the behaviour the rule detects.
- [ ] Licensing: no verbatim copyrighted text (industry codes especially).
- [ ] `verification_notes` updated, and `verified_on` set to the review date.

## Optional CI step: weekly source drift check

Another workstream owns `.github/workflows/ci.yml`, so this is a suggestion only. A scheduled job that fails (exit
code 2) when any cited source changes against `src/data/sources.lock.json`:

```yaml
name: corpus-freshness
on:
  schedule:
    - cron: "0 22 * * 0"   # weekly, Monday 08:00 AEST
  workflow_dispatch:
jobs:
  diff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {{ python-version: "3.12" }}
      - run: pip install httpx
      - run: python scripts/check_corpus_freshness.py staleness --fail-on-unverified
      - run: python scripts/check_corpus_freshness.py diff
```

## Instruments
"""

SIGN_OFF = """
## Sign-off

| Reviewer | Date | Scope (instruments) | Outcome (approved / changes required) |
| --- | --- | --- | --- |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
"""


def _cell(value: Any) -> str:
    return str(value if value not in (None, "") else "-").replace("|", "\\|").replace("\n", " ")


def render_review_pack(instruments: List[Dict[str, Any]], today: Optional[date] = None) -> str:
    today = today or date.today()
    clauses = sum(len(i.get("clauses", [])) for i in instruments)
    parts = [REVIEW_INTRO.format(today=today.isoformat(), count=len(instruments), clauses=clauses)]
    by_reg: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for inst in instruments:
        by_reg[str(inst.get("regulator", ""))].append(inst)
    for reg in sorted(by_reg):
        parts.append(f"\n### {reg}\n")
        parts.append("| Code | Regulator | Status | Enforceability | Clauses | Verified on | Text kind | Source |")
        parts.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for i in by_reg[reg]:
            parts.append("| " + " | ".join([
                _cell(i.get("code")), _cell(i.get("regulator")), _cell(i.get("status")),
                _cell(i.get("enforceability")), str(len(i.get("clauses", []))),
                _cell(i.get("verified_on") or "UNVERIFIED"), _cell(i.get("text_kind")), _cell(i.get("source_url")),
            ]) + " |")
        flagged = [(i, uncertainty_items(i.get("verification_notes", ""))) for i in by_reg[reg]]
        flagged = [(i, items) for i, items in flagged if items or not (i.get("verified_on") or "").strip()]
        if flagged:
            parts.append("\nNeeds confirmation:\n")
            for i, items in flagged:
                if not (i.get("verified_on") or "").strip():
                    parts.append(f"- **{i.get('code')}**: no `verified_on`; not verified by any reviewer.")
                for item in items:
                    parts.append(f"- **{i.get('code')}**: {item}")
    parts.append(SIGN_OFF)
    return "\n".join(parts)


def cmd_review_pack(_: argparse.Namespace) -> int:
    REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    instruments = load_instruments()
    REVIEW_PATH.write_text(render_review_pack(instruments), encoding="utf-8")
    print(f"Wrote {REVIEW_PATH} ({len(instruments)} instruments)")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    st = sub.add_parser("staleness", help="offline: list stale, unverified or uncertain instruments")
    st.add_argument("--max-age-days", type=int, default=90)
    st.add_argument("--fail-on-unverified", action="store_true", help="exit 1 if any verified_on is empty")
    st.set_defaults(func=cmd_staleness)
    sub.add_parser("snapshot", help="online: fetch sources and write the lock file").set_defaults(func=cmd_snapshot)
    sub.add_parser("diff", help="online: compare sources to the lock (exit 2 on change)").set_defaults(func=cmd_diff)
    sub.add_parser("review-pack", help="offline: write docs/CORPUS_REVIEW.md").set_defaults(func=cmd_review_pack)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
