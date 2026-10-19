"""Measure detection on the blind corpus, optionally with the semantic judge enabled.

    .venv/bin/python scripts/evaluate_detection.py --split holdout
    .venv/bin/python scripts/evaluate_detection.py --split holdout --judge ollama --model qwen3:14b

Writes reports/detection_metrics_<split>_<mode>.md and prints a summary. Rules-only runs are offline; judge runs call
the configured provider once per record.
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="holdout", choices=["dev", "holdout"])
    ap.add_argument("--judge", default="", help="anthropic | openai | ollama (default: rules only)")
    ap.add_argument("--model", default="")
    ap.add_argument("--timeout", default="180")
    args = ap.parse_args()

    if args.judge:
        os.environ["GUARDIAN_JUDGE_PROVIDER"] = args.judge
        os.environ["GUARDIAN_JUDGE_TIMEOUT"] = args.timeout
        if args.model:
            os.environ["GUARDIAN_JUDGE_MODEL"] = args.model

    from src.tools.agent_auditor import audit_agent_interaction_for_breach

    records = [json.loads(l) for l in (ROOT / "tests/corpus/insurance" / f"{args.split}.jsonl").read_text().splitlines() if l.strip()]
    stats = {k: defaultdict(int) for k in ("tp_rule", "tp_judge", "fn", "fp_rule", "fp_judge")}
    errors, misses, false_alarms = 0, [], []
    started = time.time()
    for i, rec in enumerate(records, 1):
        res = audit_agent_interaction_for_breach(
            rec["agent_role"], rec["user_prompt"], rec["agent_response"],
            context={} if args.judge else {"judge": False}, sector=rec.get("sector"),
        )
        if res["coverage_scope"]["judge"].startswith("error"):
            errors += 1
        rule_found = {v["category"] for v in res["apra_violations"]} | {
            f["category"] for f in res["review_flags"] if f["detection"] != "semantic_judge"}
        judge_found = {f["category"] for f in res["review_flags"] if f["detection"] == "semantic_judge"}
        cat = rec["category"]
        if rec["label"] == "breach":
            if cat in rule_found:
                stats["tp_rule"][cat] += 1
            elif cat in judge_found:
                stats["tp_judge"][cat] += 1
            else:
                stats["fn"][cat] += 1
                misses.append(rec)
        else:
            for c in rule_found:
                stats["fp_rule"][c] += 1
                false_alarms.append(("rule", c, rec))
            for c in judge_found - rule_found:
                stats["fp_judge"][c] += 1
                false_alarms.append(("judge", c, rec))
        if i % 25 == 0:
            print(f"{i}/{len(records)} records, {time.time() - started:.0f}s", flush=True)

    cats = sorted({r["category"] for r in records if r["label"] == "breach"})
    tot = {k: sum(v.values()) for k, v in stats.items()}
    breaches = tot["tp_rule"] + tot["tp_judge"] + tot["fn"]
    rule_recall = tot["tp_rule"] / breaches
    layered_recall = (tot["tp_rule"] + tot["tp_judge"]) / breaches
    rule_precision = tot["tp_rule"] / max(1, tot["tp_rule"] + tot["fp_rule"])
    layered_precision = (tot["tp_rule"] + tot["tp_judge"]) / max(1, tot["tp_rule"] + tot["tp_judge"] + tot["fp_rule"] + tot["fp_judge"])

    mode = f"judge-{args.judge}-{args.model or 'default'}" if args.judge else "rules"
    lines = [
        f"# Detection metrics: {args.split}, {mode}\n",
        f"- Records: {len(records)} ({breaches} breach lines); judge errors: {errors}; runtime {time.time() - started:.0f}s",
        f"- Rules only: recall {rule_recall:.0%}, precision {rule_precision:.0%}",
    ]
    if args.judge:
        lines.append(f"- Rules plus judge (judge hits are REVIEW flags): recall {layered_recall:.0%}, precision {layered_precision:.0%}")
    lines += ["", "| Category | Rule TP | Judge TP | FN | Rule FP | Judge FP |", "| :--- | ---: | ---: | ---: | ---: | ---: |"]
    for c in cats:
        lines.append(f"| {c} | {stats['tp_rule'][c]} | {stats['tp_judge'][c]} | {stats['fn'][c]} | {stats['fp_rule'][c]} | {stats['fp_judge'][c]} |")
    lines.append("\n## Misses\n")
    lines += [f"- `{m['id']}` {m['category']}: {m['agent_response'][:140]}" for m in misses] or ["- None"]
    lines.append("\n## False alarms on clean lines\n")
    lines += [f"- `{r['id']}` {src} flagged {c}: {r['agent_response'][:140]}" for src, c, r in false_alarms] or ["- None"]
    out = ROOT / "reports" / f"detection_metrics_{args.split}_{mode.replace(':', '-')}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:5]))
    print(f"Report: {out}")


if __name__ == "__main__":
    main()
