#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 engine_verdicts + human_labels 计算 agreement / Cohen's κ / 每类 P/R/F1。"""
import argparse, json
from collections import Counter

LABELS = ["correct", "miss", "confusion", "improper_persistence",
          "improper_reuse", "not_evaluable"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eng", default="tests/labels/engine_verdicts.json")
    ap.add_argument("--hum", default="tests/labels/human_labels.json")
    ap.add_argument("--out", default="tests/labels/agreement_report.json")
    args = ap.parse_args()
    eng_list = json.load(open(args.eng, encoding="utf-8"))
    human = json.load(open(args.hum, encoding="utf-8"))["labels"]
    y_e = [it["engine_verdict"] for it in eng_list]
    y_h = [human.get(it["id"]) for it in eng_list]
    n = len(y_e)
    agree = sum(1 for a, b in zip(y_e, y_h) if a == b)
    po = agree / n
    pe = sum((y_e.count(l) / n) * (y_h.count(l) / n) for l in LABELS)
    kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0

    def prf(cls):
        tp = sum(1 for a, b in zip(y_e, y_h) if a == cls and b == cls)
        fp = sum(1 for a, b in zip(y_e, y_h) if a == cls and b != cls)
        fn = sum(1 for a, b in zip(y_e, y_h) if a != cls and b == cls)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) else 0.0
        return round(p, 4), round(r, 4), round(f1, 4)

    report = {
        "n": n,
        "agreement": round(po, 4),
        "cohen_kappa": round(kappa, 4),
        "per_class": {l: dict(zip(("precision", "recall", "f1"), prf(l))) for l in LABELS},
        "engine_distribution": dict(Counter(y_e)),
        "human_distribution": dict(Counter(y_h)),
        "anchors": {
            "AMA-Bench LLM-judge human agreement": 0.927,
            "Memora 3-judge majority-vote": 0.883,
        },
    }
    json.dump(report, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("n=%d agreement=%.4f kappa=%.4f -> %s" % (n, po, kappa, args.out))

if __name__ == "__main__":
    main()
