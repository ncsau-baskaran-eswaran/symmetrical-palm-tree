"""Detection quality on a blind paraphrase corpus (rules only, judge disabled).

The corpus in tests/corpus/insurance/ was written without access to the rule patterns. `dev.jsonl` is used to tune
rules; `holdout.jsonl` is never tuned against and reports honest generalisation. Results are written to
reports/detection_metrics.md so buyers can see measured recall and precision per category.
"""

import json
from collections import defaultdict
from pathlib import Path

import pytest

from src.tools.agent_auditor import audit_agent_interaction_for_breach

CORPUS = Path(__file__).parent / "corpus" / "insurance"
REPORT = Path(__file__).parent.parent / "reports" / "detection_metrics.md"

# Floors are regression guards set just below measured performance, and only ever raised. Dev is tuned against,
# so its numbers are optimistic. Holdout (rules only) measured 32% recall and 93% precision on 2026-10-19: the rules are
# precise but do not generalise to unseen phrasing, which is why the semantic judge and REVIEW lane exist.
FLOORS = {
    "dev": {"recall": 0.95, "precision": 0.95},
    "holdout": {"recall": 0.30, "precision": 0.90},
}


def _load(split):
    path = CORPUS / f"{split}.jsonl"
    if not path.exists():
        pytest.skip(f"{path} not present")
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _detected(record):
    res = audit_agent_interaction_for_breach(
        agent_role=record["agent_role"],
        user_prompt=record["user_prompt"],
        agent_response=record["agent_response"],
        context={"judge": False},
        sector=record.get("sector"),
    )
    return {v["category"] for v in res["apra_violations"]} | {f["category"] for f in res["review_flags"]}


def evaluate(split):
    records = _load(split)
    tp, fn, fp = defaultdict(int), defaultdict(int), defaultdict(int)
    misses, false_alarms, secondary = [], [], []
    for rec in records:
        found = _detected(rec)
        cat = rec["category"]
        if rec["label"] == "breach":
            if cat in found:
                tp[cat] += 1
            else:
                fn[cat] += 1
                misses.append(rec)
            # The corpus is single-label; extra categories on a breach line are often genuine co-occurring breaches
            # (an agent-issued decline that also omits AFCA details), so they are reported, not scored as false alarms.
            secondary += [(other, rec) for other in found - {cat}]
            continue
        for other in found:
            fp[other] += 1
            false_alarms.append((other, rec))
    cats = sorted({r["category"] for r in records if r["label"] == "breach"})
    rows = []
    for c in cats:
        recall = tp[c] / (tp[c] + fn[c]) if tp[c] + fn[c] else 1.0
        precision = tp[c] / (tp[c] + fp[c]) if tp[c] + fp[c] else 1.0
        rows.append((c, tp[c], fn[c], fp[c], recall, precision))
    total_tp, total_fn, total_fp = sum(tp.values()), sum(fn.values()), sum(fp.values())
    overall = {
        "recall": total_tp / (total_tp + total_fn) if total_tp + total_fn else 1.0,
        "precision": total_tp / (total_tp + total_fp) if total_tp + total_fp else 1.0,
        "records": len(records),
        "clean_records": sum(1 for r in records if r["label"] == "clean"),
        "secondary_detections": len(secondary),
    }
    return rows, overall, misses, false_alarms


def _write_report(results):
    lines = [
        "# Detection metrics (rules only)\n",
        "Measured on a blind paraphrase corpus written without access to the rule patterns. `dev` is used for tuning;",
        "`holdout` is never tuned against. A missed breach here is a breach the deterministic screen would let through;",
        "the optional semantic judge and human review exist for exactly that gap. False positives are counted on clean",
        "(compliant) lines only; extra categories raised on a breach line are listed as secondary detections because the",
        "corpus carries one label per line and many replies genuinely commit two breaches.\n",
    ]
    for split, (rows, overall, misses, false_alarms) in results.items():
        lines.append(
            f"## {split}: recall {overall['recall']:.0%}, precision {overall['precision']:.0%} "
            f"({overall['records']} records, {overall['clean_records']} clean, {overall['secondary_detections']} secondary detections)\n"
        )
        lines.append("| Category | TP | FN | FP | Recall | Precision |")
        lines.append("| :--- | ---: | ---: | ---: | ---: | ---: |")
        for c, t, n, f, r, p in rows:
            lines.append(f"| {c} | {t} | {n} | {f} | {r:.0%} | {p:.0%} |")
        if split == "holdout" and misses:
            lines.append("\n**Holdout misses** (not tuned against):\n")
            for m in misses:
                lines.append(f"- `{m['id']}` {m['category']}: {m['agent_response'][:140]}")
        if split == "holdout" and false_alarms:
            lines.append("\n**Holdout false alarms:**\n")
            for cat, m in false_alarms:
                lines.append(f"- `{m['id']}` flagged {cat}: {m['agent_response'][:140]}")
        lines.append("")
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(lines))


@pytest.fixture(scope="module")
def results():
    out = {split: evaluate(split) for split in ("dev", "holdout")}
    _write_report(out)
    return out


@pytest.mark.parametrize("split", ["dev", "holdout"])
def test_detection_meets_floors(results, split):
    _rows, overall, misses, false_alarms = results[split]
    floor = FLOORS[split]
    assert overall["recall"] >= floor["recall"], f"{split} recall {overall['recall']:.2f}; misses: {[m['id'] for m in misses]}"
    assert overall["precision"] >= floor["precision"], f"{split} precision {overall['precision']:.2f}; false alarms: {[(c, m['id']) for c, m in false_alarms]}"
