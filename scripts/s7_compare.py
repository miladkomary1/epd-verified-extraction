"""Step 7: score LLM extraction against registry ground truth.

Match rule: nonzero -> relative error <= 2.5% (PDF prints rounded registry values);
zero -> |llm| <= 1e-9. Taxonomy for mismatches: ROUND (2.5-10%), MAG (>10x or sign),
COL (llm value matches the gt value of a different module of the same indicator), OTHER.
"""
import json, os, sys, re
from collections import defaultdict

RUN = sys.argv[1] if len(sys.argv) > 1 else "run1"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")

INDICATORS = ["GWP-total", "GWP-fossil", "GWP-biogenic", "GWP-luluc", "ODP", "AP",
              "EP-freshwater", "EP-marine", "EP-terrestrial", "POCP", "ADPE", "ADPF", "WDP",
              "PERT", "PENRT", "FW", "SM", "HWD", "NHWD", "RWD"]

def norm_mod(m):
    m = str(m).upper().replace(" ", "").replace("_", "-").replace("–", "-")
    m = {"A1-3": "A1-A3", "A1A3": "A1-A3", "A1TOA3": "A1-A3"}.get(m, m)
    return m

def matches(llm, gt):
    if gt == 0:
        return abs(llm) <= 1e-9
    return abs(llm - gt) / abs(gt) <= 0.025

def classify(llm, gt, gt_modules):
    if gt != 0 and llm != 0:
        rel = abs(llm - gt) / abs(gt)
        if rel <= 0.10:
            return "ROUND"
        if (llm < 0) != (gt < 0):
            return "SIGN"
    for om, ov in gt_modules.items():
        if ov != 0 and abs(llm - ov) / abs(ov) <= 0.025:
            return f"COL(={om})"
    if gt != 0 and llm != 0 and (abs(llm / gt) >= 10 or abs(llm / gt) <= 0.1):
        return "MAG"
    return "OTHER"

per_item, per_ind, per_mod = [], defaultdict(lambda: [0, 0, 0]), defaultdict(lambda: [0, 0, 0])
errors = []
tot = {"gt_slots": 0, "populated": 0, "matched": 0, "extra": 0}

for uuid in sorted(os.listdir(CORPUS)):
    d = os.path.join(CORPUS, uuid)
    lp = os.path.join(d, f"llm_{RUN}.json")
    if not os.path.exists(lp):
        continue
    gt = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))
    llm = json.load(open(lp, encoding="utf8"))
    llm_ind = {k: v for k, v in (llm.get("indicators") or {}).items()}
    it = {"name": gt["name"][:36], "gt_slots": 0, "pop": 0, "match": 0, "extra": 0}
    for code in INDICATORS:
        g = gt["indicators"].get(code)
        if not g:
            continue
        gmods = {norm_mod(k): v for k, v in g["modules"].items()}
        lvals = {}
        if code in llm_ind and isinstance(llm_ind[code], dict):
            raw = llm_ind[code].get("values", llm_ind[code])
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if isinstance(v, (int, float)):
                        lvals[norm_mod(k)] = float(v)
    # compare
        for m, gv in gmods.items():
            it["gt_slots"] += 1
            per_ind[code][0] += 1; per_mod[m][0] += 1
            if m in lvals:
                it["pop"] += 1
                per_ind[code][1] += 1; per_mod[m][1] += 1
                if matches(lvals[m], gv):
                    it["match"] += 1
                    per_ind[code][2] += 1; per_mod[m][2] += 1
                else:
                    errors.append({"item": gt["name"][:30], "ind": code, "mod": m,
                                   "llm": lvals[m], "gt": gv,
                                   "class": classify(lvals[m], gv, gmods)})
        it["extra"] += sum(1 for m in lvals if m not in gmods)
    per_item.append(it)
    for k in ("gt_slots", "extra"):
        tot[k] += it[k]
    tot["populated"] += it["pop"]; tot["matched"] += it["match"]

print(f"=== {RUN}: {len(per_item)} items ===")
print(f"{'item':38} slots pop match  acc")
for it in per_item:
    acc = it["match"] / it["pop"] * 100 if it["pop"] else 0
    print(f"{it['name']:38} {it['gt_slots']:5} {it['pop']:4} {it['match']:5} {acc:5.1f}%")

cov = tot["populated"] / tot["gt_slots"] * 100
acc = tot["matched"] / tot["populated"] * 100 if tot["populated"] else 0
rec = tot["matched"] / tot["gt_slots"] * 100
print(f"\nTOTAL gt slots={tot['gt_slots']}  populated={tot['populated']} ({cov:.1f}%)  "
      f"matched={tot['matched']}  precision-on-populated={acc:.2f}%  recall={rec:.2f}%  "
      f"extra-slots-not-in-gt={tot['extra']}")

print("\n=== per module ===")
for m in sorted(per_mod, key=lambda x: (len(x), x)):
    g, p, c = per_mod[m]
    print(f"{m:7} gt={g:4} pop={p:4} match={c:4}  acc={c/p*100 if p else 0:5.1f}%")

print("\n=== per indicator (worst first) ===")
rows = [(c, *per_ind[c]) for c in per_ind]
rows.sort(key=lambda r: (r[3] / r[2]) if r[2] else 1)
for code, g, p, c in rows:
    print(f"{code:15} gt={g:4} pop={p:4} match={c:4}  acc={c/p*100 if p else 0:5.1f}%")

print(f"\n=== mismatches: {len(errors)} ===")
cls = defaultdict(int)
for e in errors:
    cls[re.sub(r'\(.*', '', e['class'])] += 1
print(dict(cls))
for e in errors[:25]:
    print(f"{e['item']:32} {e['ind']:14} {e['mod']:6} llm={e['llm']:<12.6g} gt={e['gt']:<12.6g} {e['class']}")

json.dump({"totals": tot, "coverage_pct": cov, "precision_pct": acc, "recall_pct": rec,
           "errors": errors}, open(os.path.join(ROOT, f"score_{RUN}.json"), "w"), indent=1)
