"""Step 14: unified scoring engine — raw metrics + grounding gate + arithmetic gate.

usage: py s14_score.py <scope> <run1> [run2 ...]
scope: core | ext | all
Writes data/eval_<run>.json per run and prints aggregate mean +/- 95% CI when >2 runs.
"""
import json, os, sys, math
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")
QUAR = {"215ccde9-9317-4c9c-88b7-afd71e5d2102", "f518d04d-4805-4d97-b457-9909e508751ab",
        "f518d04d-4805-4d97-b457-9920226f3ff4"}

CODES = ["GWP-total", "GWP-fossil", "GWP-biogenic", "GWP-luluc", "ODP", "AP",
         "EP-freshwater", "EP-marine", "EP-terrestrial", "POCP", "ADPE", "ADPF", "WDP",
         "PERE", "PERM", "PERT", "PENRE", "PENRM", "PENRT",
         "SM", "RSF", "NRSF", "FW", "HWD", "NHWD", "RWD"]
IDENTITIES = [("PERT", "PERE", "PERM"), ("PENRT", "PENRE", "PENRM"),
              ("GWP-total", "GWP-fossil", "GWP-biogenic", "GWP-luluc")]

def norm_mod(m):
    m = str(m).upper().replace(" ", "").replace("_", "-").replace("–", "-")
    return {"A1-3": "A1-A3", "A1A3": "A1-A3", "A1TOA3": "A1-A3"}.get(m, m)

def renderings(v):
    outs = set()
    if v == 0:
        return {"0.00E+0", "0.00E+00", "0,00", " 0 ", "0.0", " 0\n"}
    neg = "-" if v < 0 else ""
    av = abs(v)
    exp = math.floor(math.log10(av))
    for sig in (2, 3, 4):
        mant = round(av / 10**exp, sig - 1)
        e = exp
        if mant >= 10:
            mant /= 10; e += 1
        dec = f"{mant:.{sig-1}f}"
        dec2 = dec.rstrip("0").rstrip(".") if "." in dec else dec
        sign = "+" if e >= 0 else "-"
        for ds in {dec, dec2, dec.replace(".", ","), dec2.replace(".", ",")}:
            for es in (f"{abs(e)}", f"{abs(e):02d}"):
                outs.add(f"{neg}{ds}E{sign}{es}")
        r = round(v, max(0, sig - 1 - exp))
        outs.add(f"{r:g}"); outs.add(f"{r:g}".replace(".", ","))
    return outs

def matches(llm, gt):
    if gt == 0:
        return abs(llm) <= 1e-9
    return abs(llm - gt) / abs(gt) <= 0.025

def load_llm(path):
    llm = json.load(open(path, encoding="utf8"))
    out = {}
    for code, obj in (llm.get("indicators") or {}).items():
        if not isinstance(obj, dict):
            continue
        raw = obj.get("values", obj)
        if isinstance(raw, dict):
            vals = {}
            for k, v in raw.items():
                if isinstance(v, (int, float)):
                    vals[norm_mod(k)] = float(v)
                elif isinstance(v, str):
                    try: vals[norm_mod(k)] = float(v.replace(",", "."))
                    except ValueError: pass
            if vals:
                out[code] = vals
    return out

def arithmetic_flags(llm):
    """Return set of (code, module) withheld by identity checks."""
    flags = set()
    for ident in IDENTITIES:
        total, comps = ident[0], ident[1:]
        tvals = llm.get(total, {})
        for m, t in tvals.items():
            cvals = [llm.get(c, {}).get(m) for c in comps]
            if any(c is None for c in cvals):
                continue
            ss = sum(cvals)
            if abs(t - ss) > max(0.04 * max(abs(t), abs(ss)), 1e-9):
                flags.add((total, m))
                for c in comps:
                    flags.add((c, m))
    return flags

def score_run(run, scope):
    core18 = sorted(u for u in os.listdir(CORPUS)
                    if os.path.exists(os.path.join(CORPUS, u, "llm_run1.json")))
    res = {"raw": defaultdict(int), "gated": defaultdict(int), "errors": [],
           "gated_errors": [], "per_item": []}
    for uuid in sorted(os.listdir(CORPUS)):
        if uuid in QUAR:
            continue
        if scope == "core" and uuid not in core18:
            continue
        if scope == "ext" and uuid in core18:
            continue
        d = os.path.join(CORPUS, uuid)
        lp = os.path.join(d, f"llm_{run}.json")
        gp = os.path.join(d, "gt.json")
        if not (os.path.exists(lp) and os.path.exists(gp)):
            continue
        gt = json.load(open(gp, encoding="utf8"))
        llm = load_llm(lp)
        text = open(os.path.join(d, "pdftext.txt"), encoding="utf8").read()
        for ch in ("\xad", "−", "–"):
            text = text.replace(ch, "-")
        text = text.replace("\xa0", " ")
        aflags = arithmetic_flags(llm)
        it = defaultdict(int)
        for code in CODES:
            g = gt["indicators"].get(code)
            if not g:
                continue
            gmods = {norm_mod(k): v for k, v in g["modules"].items()}
            lvals = llm.get(code, {})
            for m, gv in gmods.items():
                res["raw"]["gt_slots"] += 1; it["gt_slots"] += 1
                if m not in lvals:
                    continue
                v = lvals[m]
                ok = matches(v, gv)
                res["raw"]["populated"] += 1; it["pop"] += 1
                if ok: res["raw"]["matched"] += 1; it["match"] += 1
                else: res["errors"].append({"item": gt["name"][:30], "code": code, "mod": m,
                                            "llm": v, "gt": gv})
                # gates
                grounded = any(r in text for r in renderings(v))
                withheld = (not grounded) or ((code, m) in aflags)
                if not withheld:
                    res["gated"]["populated"] += 1
                    if ok: res["gated"]["matched"] += 1
                    else: res["gated_errors"].append({"item": gt["name"][:30], "code": code,
                                                      "mod": m, "llm": v, "gt": gv})
                else:
                    if ok: res["gated"]["correct_withheld"] += 1
                    else: res["gated"]["error_withheld"] += 1
        res["per_item"].append({"uuid": uuid, "name": gt["name"][:40], **it})
    r, g = res["raw"], res["gated"]
    out = {
        "run": run, "scope": scope, "n_items": len(res["per_item"]),
        "gt_slots": r["gt_slots"],
        "coverage_pct": r["populated"] / r["gt_slots"] * 100 if r["gt_slots"] else 0,
        "precision_pct": r["matched"] / r["populated"] * 100 if r["populated"] else 0,
        "recall_pct": r["matched"] / r["gt_slots"] * 100 if r["gt_slots"] else 0,
        "n_errors": len(res["errors"]),
        "gated_coverage_pct": g["populated"] / r["gt_slots"] * 100 if r["gt_slots"] else 0,
        "gated_precision_pct": g["matched"] / g["populated"] * 100 if g["populated"] else 0,
        "gated_errors_surfaced": len(res["gated_errors"]),
        "errors_withheld": g["error_withheld"], "correct_withheld": g["correct_withheld"],
        "errors": res["errors"][:60], "gated_errors": res["gated_errors"][:60],
        "per_item": res["per_item"],
    }
    json.dump(out, open(os.path.join(ROOT, f"eval_{run}_{scope}.json"), "w"), indent=1)
    return out

def mean_ci(vals):
    n = len(vals)
    m = sum(vals) / n
    if n < 2:
        return m, 0.0
    sd = math.sqrt(sum((x - m) ** 2 for x in vals) / (n - 1))
    t = {2: 12.71, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 7: 2.447, 8: 2.365,
         9: 2.306, 10: 2.262}.get(n, 1.96)
    return m, t * sd / math.sqrt(n)

if __name__ == "__main__":
    scope = sys.argv[1]
    runs = sys.argv[2:]
    outs = [score_run(r, scope) for r in runs]
    for o in outs:
        print(f"{o['run']:8} n={o['n_items']:3} slots={o['gt_slots']:5} "
              f"cov={o['coverage_pct']:.1f}% prec={o['precision_pct']:.2f}% err={o['n_errors']:2} | "
              f"gated: cov={o['gated_coverage_pct']:.1f}% prec={o['gated_precision_pct']:.2f}% "
              f"errSurf={o['gated_errors_surfaced']} errHeld={o['errors_withheld']} okHeld={o['correct_withheld']}")
    if len(outs) > 2:
        print("\n=== aggregate (mean ± 95% CI) ===")
        for k in ("coverage_pct", "precision_pct", "recall_pct", "gated_coverage_pct",
                  "gated_precision_pct", "gated_errors_surfaced", "n_errors"):
            m, ci = mean_ci([o[k] for o in outs])
            print(f"{k:24} {m:8.2f} ± {ci:.2f}")
