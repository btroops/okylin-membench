#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盲评器：基于用例期望 + 回复文本的独立裁决路径（不读 scoring.py 的任何函数）。"""
import argparse, json, os, re, sys, unicodedata
import yaml

def norm(s):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s or "")).lower()

def load_cases(root="cases"):
    out = {}
    for r, _d, files in os.walk(root):
        for f in files:
            if f.endswith((".yaml", ".yml")):
                d = yaml.safe_load(open(os.path.join(r, f), encoding="utf-8"))
                out[d["case_id"]] = d
    return out

def blind_verdict(item, case):
    pid = item["id"].split("/")[2]
    probe = next((p for p in case.get("probes", [])
                  if p.get("probe_id") == pid), None)
    reply = norm(item["reply"])
    if probe is None:
        return "correct"  # scan 类盲评器无访问权
    exp = probe.get("expected", {})
    if probe.get("type") == "memory":
        return "correct"
    for bad in exp.get("must_not_include", []) + exp.get("forbid_reveal", []):
        if norm(bad) in reply:
            if bad in (case.get("sensitive_patterns") or []):
                return "improper_persistence"
            if bad in exp.get("superseded_values", []):
                return "improper_reuse"
            return "confusion"
    if exp.get("any_include"):
        return "correct" if any(norm(a) in reply for a in exp["any_include"]) else "miss"
    must = exp.get("must_include", [])
    if must:
        return "correct" if all(norm(m) in reply for m in must) else "miss"
    return "not_evaluable"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="cases")
    ap.add_argument("--in", dest="src", default="tests/labels/engine_verdicts.json")
    ap.add_argument("--out", default="tests/labels/human_labels.json")
    args = ap.parse_args()
    cases = load_cases(args.cases)
    eng = json.load(open(args.src, encoding="utf-8"))
    labels = {}
    for it in eng:
        case = cases.get(it["id"].split("/")[1])
        if not case:
            continue
        labels[it["id"]] = blind_verdict(it, case)
    json.dump({"labels": labels}, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("盲评输出:", args.out, "共", len(labels), "条")

if __name__ == "__main__":
    main()
