#!/usr/bin/env python3
"""Code-aware ("embedded") APRA control analysis of an agent's source.

Examples
--------
    uv run python run_code_audit.py --fixture wild-banking
    uv run python run_code_audit.py --file src/agent_service/brains.py --scope _in_band
"""

import argparse

from src.code_auditor.analyzer import analyze_fixture, analyze_scope, FIXTURES

BADGE = {
    "EXPOSURE": "🔴 EXPOSURE",
    "CONTROL_MISSING": "🟠 MISSING",
    "CONTROL_VERIFIED": "🟢 VERIFIED",
    "CONTROL_INDICATOR": "⚪ INDICATOR",
    "UNVERIFIABLE_LOCALLY": "🔵 UNVERIFIABLE",
}


def main():
    p = argparse.ArgumentParser(description="White-box code-aware APRA control analyzer.")
    p.add_argument("--fixture", "-x", choices=list(FIXTURES), help="Built-in demo fixture")
    p.add_argument("--file", "-f", help="Path to a source file")
    p.add_argument("--scope", "-s", help="Class or function name to scope to")
    args = p.parse_args()

    if args.fixture:
        report = analyze_fixture(args.fixture)
    elif args.file:
        report = analyze_scope(args.file, args.scope)
    else:
        p.error("Provide --fixture or --file")

    t = report["target"]
    s = report["summary"]
    print("=" * 74)
    print(f"  CODE-AWARE ANALYSIS · {t.get('label', t['file'])}")
    print(f"  Source: {t['file']}" + (f"  (scope: {t['scope']})" if t.get("scope") else ""))
    print(f"  Code posture: {report['code_posture']}   "
          f"exposures={s['exposures']} verified={s['controls_verified']} missing={s['controls_missing']}")
    print("=" * 74)
    for f in report["findings"]:
        print(f"\n{BADGE.get(f['status'], f['status'])}  [{f['standard']} {f['clause']}]  {f['title']}")
        print(f"    {f['detail']}")
        for ev in f["evidence"]:
            print(f"    ↳ {ev['file']}:{ev['line']}  {ev.get('snippet','')}")
        if f.get("remediation"):
            print(f"    fix: {f['remediation']}")
    print()


if __name__ == "__main__":
    main()
