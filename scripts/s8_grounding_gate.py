"""Step 8: deterministic source-grounding gate over LLM outputs.

A populated value passes the gate iff one of its common printed renderings
(scientific/decimal, point/comma, 2-4 sig figs, 1-2 digit exponent) occurs
verbatim in the PDF text. Reports: (a) how many true errors the gate flags,
(b) how many correct values it wrongly withholds (the coverage cost).
"""
import json, os, sys, math
from collections import defaultdict

RUN = sys.argv[1] if len(sys.argv) > 1 else "run2"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")

INDICATORS = ["GWP-total", "GWP-fossil", "GWP-biogenic", "GWP-luluc", "ODP", "AP",
              "EP-freshwater", "EP-marine", "EP-terrestrial", "POCP", "ADPE", "ADPF", "WDP",
              "PERT", "PENRT", "FW", "SM", "HWD", "NHWD", "RWD"]

def norm_mod(m):
    m = str(m).upper().replace(" ", "").replace("_", "-").replace("–", "-")
    return {"A1-3": "A1-A3", "A1A3": "A1-A3"}.get(m, m)

def renderings(v):
    outs = set()
    if v == 0:
        return {"0.00E+0", "0.00E+00", "0,00", " 0 ", "0.0"}
    neg = "-" if v < 0 else ""
    av = abs(v)
    exp = math.floor(math.log10(av))
    for sig in (2, 3, 4):
        mant = round(av / 10**exp, sig - 1)
        e = exp
        if mant >= 10:
            mant /= 10; e += 1
        dec = f"{mant:.{sig-1}f}"
        # trailing-zero-stripped variant (1.4E-01 for 0.14 at 3 sig figs)
        dec2 = dec.rstrip("0").rstrip(".") if "." in dec else dec
        sign = "+" if e >= 0 else "-"
        for ds in {dec, dec2, dec.replace(".", ","), dec2.replace(".", ",")}:
            for es in (f"{abs(e)}", f"{abs(e):02d}"):
                outs.add(f"{neg}{ds}E{sign}{es}")
        r = round(v, max(0, sig - 1 - exp))
        outs.add(f"{r:g}")
        outs.add(f"{r:g}".replace(".", ","))
    return outs

def matches(llm, gt):
    if gt == 0:
        return abs(llm) <= 1e-9
    return abs(llm - gt) / abs(gt) <= 0.025

stats = {"correct_pass": 0, "correct_flagged": 0, "error_pass": 0, "error_flagged": 0}
flagged_errors, passed_errors, flagged_correct = [], [], []

for uuid in sorted(os.listdir(CORPUS)):
    d = os.path.join(CORPUS, uuid)
    lp = os.path.join(d, f"llm_{RUN}.json")
    if not os.path.exists(lp):
        continue
    gt = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))
    llm = json.load(open(lp, encoding="utf8")).get("indicators", {})
    text = open(os.path.join(d, "pdftext.txt"), encoding="utf8").read()
    for ch in ("\xad", "\u2212", "\u2013"):   # soft hyphen, minus, en dash -> hyphen
        text = text.replace(ch, "-")
    text = text.replace("\xa0", " ")
    for code in INDICATORS:
        g = gt["indicators"].get(code)
        if not g or code not in llm or not isinstance(llm[code], dict):
            continue
        gmods = {norm_mod(k): v for k, v in g["modules"].items()}
        raw = llm[code].get("values", llm[code])
        if not isinstance(raw, dict):
            continue
        for m, v in raw.items():
            if not isinstance(v, (int, float)):
                continue
            mm = norm_mod(m)
            if mm not in gmods:
                continue
            grounded = any(r in text for r in renderings(float(v)))
            correct = matches(float(v), gmods[mm])
            key = ("correct" if correct else "error") + ("_pass" if grounded else "_flagged")
            stats[key] += 1
            rec = f"{gt['name'][:28]:30} {code:12} {mm:6} llm={v:<12.6g} gt={gmods[mm]:<12.6g}"
            if not correct and grounded:
                passed_errors.append(rec)
            elif not correct and not grounded:
                flagged_errors.append(rec)
            elif correct and not grounded:
                flagged_correct.append(rec)

print(f"=== grounding gate on {RUN} ===")
print(stats)
n_err = stats["error_pass"] + stats["error_flagged"]
n_cor = stats["correct_pass"] + stats["correct_flagged"]
print(f"errors flagged by gate: {stats['error_flagged']}/{n_err}")
print(f"correct values withheld by gate (coverage cost): {stats['correct_flagged']}/{n_cor} "
      f"({stats['correct_flagged']/n_cor*100:.2f}%)")
print("\n-- errors CAUGHT by grounding gate:")
for r in flagged_errors: print("  ", r)
print("-- errors that PASS grounding (value exists in doc, wrong slot -> needs arithmetic gate):")
for r in passed_errors: print("  ", r)
print("-- correct values withheld (first 10):")
for r in flagged_correct[:10]: print("  ", r)
