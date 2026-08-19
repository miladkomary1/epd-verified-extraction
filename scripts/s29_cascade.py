# -*- coding: utf-8 -*-
"""Comment 115: deterministic parser first, LLM only where the parser fails.

Computes, entirely from data already on disk (no API calls):
  (a) parser-only coverage/agreement
  (b) LLM agreement restricted to the slots the parser could NOT parse
  (c) the cascade (parser value if present, else LLM value), raw and gated
"""
import json, os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s14_score import (CODES, norm_mod, matches, load_llm, renderings,
                       arithmetic_flags, mean_ci)

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")

def evaluate(runs, scope="core"):
    core18 = sorted(u for u in os.listdir(CORPUS)
                    if os.path.exists(os.path.join(CORPUS, u, "llm_run1.json")))
    out = []
    for run in runs:
        s = {"parser_slots": 0, "parser_ok": 0,
             "gap_slots": 0, "gap_llm_pop": 0, "gap_llm_ok": 0,
             "casc_pop": 0, "casc_ok": 0,
             "casc_gated_pop": 0, "casc_gated_ok": 0,
             "gt_slots": 0}
        for uuid in core18:
            d = os.path.join(CORPUS, uuid)
            lp = os.path.join(d, f"llm_{run}.json")
            if not os.path.exists(lp):
                continue
            gt = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))
            llm = load_llm(lp)
            det = load_llm(os.path.join(d, "llm_det.json"))
            text = open(os.path.join(d, "pdftext.txt"), encoding="utf8").read()
            for ch in ("\xad", "−", "–"):
                text = text.replace(ch, "-")
            text = text.replace("\xa0", " ")
            aflags = arithmetic_flags(llm)
            for code in CODES:
                g = gt["indicators"].get(code)
                if not g:
                    continue
                for m, gv in {norm_mod(k): v for k, v in g["modules"].items()}.items():
                    s["gt_slots"] += 1
                    dv = det.get(code, {}).get(m)
                    lv = llm.get(code, {}).get(m)
                    # (a) parser
                    if dv is not None:
                        s["parser_slots"] += 1
                        s["parser_ok"] += matches(dv, gv)
                    else:
                        # (b) the parser gap
                        s["gap_slots"] += 1
                        if lv is not None:
                            s["gap_llm_pop"] += 1
                            s["gap_llm_ok"] += matches(lv, gv)
                    # (c) cascade
                    cv = dv if dv is not None else lv
                    src = "det" if dv is not None else "llm"
                    if cv is not None:
                        s["casc_pop"] += 1
                        s["casc_ok"] += matches(cv, gv)
                        # gates: parser values are verbatim so they pass grounding;
                        # LLM values must pass grounding + arithmetic
                        if src == "det":
                            withheld = False
                        else:
                            grounded = any(r in text for r in renderings(cv))
                            withheld = (not grounded) or ((code, m) in aflags)
                        if not withheld:
                            s["casc_gated_pop"] += 1
                            s["casc_gated_ok"] += matches(cv, gv)
        out.append(s)
    return out

def pct(a, b):
    return a / b * 100 if b else 0.0

runs = [r for r in ("w1","w2","w3","w4","w5","w6","w7","w8","w9","w10") ]
res = evaluate(runs)
n = len(res)
print(f"=== Cascade analysis, core corpus, {n} Gemini runs ===\n")

r0 = res[0]
print(f"Total registry slots           : {r0['gt_slots']}")
print(f"Parser produced a value        : {r0['parser_slots']} "
      f"({pct(r0['parser_slots'], r0['gt_slots']):.1f}%)  "
      f"agreement {pct(r0['parser_ok'], r0['parser_slots']):.2f}%")
print(f"Parser gap (could not parse)   : {r0['gap_slots']} "
      f"({pct(r0['gap_slots'], r0['gt_slots']):.1f}%)   <-- Nikola's 17.9%\n")

def agg(key_num, key_den):
    vals = [pct(s[key_num], s[key_den]) for s in res]
    return mean_ci(vals)

m, ci = agg("gap_llm_pop", "gap_slots")
print(f"LLM coverage of the parser gap : {m:.1f} +/- {ci:.1f}%")
m, ci = agg("gap_llm_ok", "gap_llm_pop")
print(f"LLM agreement ON THE GAP slots : {m:.2f} +/- {ci:.2f}%   <-- answers comment 115")
m, ci = agg("gap_llm_ok", "gap_slots")
print(f"LLM recall of the gap          : {m:.1f} +/- {ci:.1f}%\n")

m, ci = agg("casc_pop", "gt_slots")
print(f"CASCADE coverage (raw)         : {m:.1f} +/- {ci:.1f}%")
m, ci = agg("casc_ok", "casc_pop")
print(f"CASCADE agreement (raw)        : {m:.2f} +/- {ci:.2f}%")
m, ci = agg("casc_gated_pop", "gt_slots")
print(f"CASCADE coverage (gated)       : {m:.1f} +/- {ci:.1f}%")
m, ci = agg("casc_gated_ok", "casc_gated_pop")
print(f"CASCADE agreement (gated)      : {m:.2f} +/- {ci:.2f}%")

# cost implication: LLM only needed for documents where parser leaves gaps
print("\n=== cost implication ===")
docs_needing_llm = 0
core18 = sorted(u for u in os.listdir(CORPUS)
                if os.path.exists(os.path.join(CORPUS, u, "llm_run1.json")))
for uuid in core18:
    d = os.path.join(CORPUS, uuid)
    gt = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))
    det = load_llm(os.path.join(d, "llm_det.json"))
    gap = 0
    for code in CODES:
        g = gt["indicators"].get(code)
        if not g:
            continue
        for m2 in {norm_mod(k) for k in g["modules"]}:
            if det.get(code, {}).get(m2) is None:
                gap += 1
    if gap:
        docs_needing_llm += 1
print(f"documents where the parser leaves at least one gap: {docs_needing_llm}/{len(core18)}")

summary = {"gt_slots": r0["gt_slots"], "parser_slots": r0["parser_slots"],
           "gap_slots": r0["gap_slots"],
           "parser_cov_pct": pct(r0["parser_slots"], r0["gt_slots"]),
           "parser_agreement_pct": pct(r0["parser_ok"], r0["parser_slots"]),
           "gap_pct": pct(r0["gap_slots"], r0["gt_slots"]),
           "gap_llm_cov": agg("gap_llm_pop", "gap_slots"),
           "gap_llm_agreement": agg("gap_llm_ok", "gap_llm_pop"),
           "cascade_cov_raw": agg("casc_pop", "gt_slots"),
           "cascade_agr_raw": agg("casc_ok", "casc_pop"),
           "cascade_cov_gated": agg("casc_gated_pop", "gt_slots"),
           "cascade_agr_gated": agg("casc_gated_ok", "casc_gated_pop"),
           "docs_needing_llm": docs_needing_llm, "n_docs": len(core18), "n_runs": n}
json.dump(summary, open(os.path.join(ROOT, "cascade.json"), "w"), indent=1)
print("\nwritten: data/cascade.json")
