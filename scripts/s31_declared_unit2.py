# -*- coding: utf-8 -*-
"""Comment 123, proper version: build the declared-unit ground truth from the ILCD
reference-flow property (Mass/Area/Volume/Number of pieces + value + unit), which is
carried locally in the exchange, and score every model's extracted declared unit."""
import json, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")

def en(sd):
    if isinstance(sd, list):
        for x in sd:
            if isinstance(x, dict) and x.get("lang") == "en":
                return x.get("value", "")
        for x in sd:
            if isinstance(x, dict):
                return x.get("value", "")
    return str(sd or "")

def ref_flow_property(pj):
    """Return (property_name, value, unit) of the reference flow, from local data."""
    for e in pj.get("exchanges", {}).get("exchange", []):
        if not e.get("referenceFlow"):
            continue
        fps = e.get("flowProperties") or []
        chosen = None
        for fp in fps:
            if fp.get("referenceFlowProperty") or fp.get("dataSetInternalID") == 0:
                chosen = fp; break
        if chosen is None and fps:
            chosen = fps[0]
        if chosen is None:
            return None
        name = en(chosen.get("referenceFlowPropertyDataSet")
                  or chosen.get("referenceToFlowPropertyDataSet", {}).get("shortDescription")
                  or chosen.get("name"))
        unit = en(chosen.get("referenceUnit") or chosen.get("unit"))
        val = chosen.get("meanValue", chosen.get("value"))
        return {"property": name, "value": val, "unit": unit,
                "amount": e.get("meanAmount"), "raw": chosen}
    return None

core18 = sorted(u for u in os.listdir(CORPUS)
                if os.path.exists(os.path.join(CORPUS, u, "llm_run1.json")))

print("=== reference flow property from LOCAL registry records ===")
have = 0
for u in core18[:8]:
    pj = json.load(open(os.path.join(CORPUS, u, "registry.json"), encoding="utf8"))
    d = ref_flow_property(pj)
    gt = json.load(open(os.path.join(CORPUS, u, "gt.json"), encoding="utf8"))
    if d:
        have += 1
        print(f"  {gt['name'][:30]:32} {d['property'][:16]:18} value={d['value']} unit='{d['unit']}'")
    else:
        print(f"  {gt['name'][:30]:32} (no local flow properties)")
print(f"  -> local flow properties present for {have}/8 sampled")

if have == 0:
    print("\nLocal records do not carry flow properties; the flow datasets must be")
    print("fetched from the registry (free) to build this ground truth. Not done here.")
    sys.exit(0)

# ---------- scoring ----------
UNITMAP = {"mass": ["kg", "t", "tonne", "ton", "g"],
           "area": ["m²", "m2", "qm", "sqm"],
           "volume": ["m³", "m3", "cbm"],
           "length": ["m", "lfm", "meter", "metre"],
           "number of pieces": ["piece", "pcs", "stk", "stück", "st", "unit", "item"]}

def unit_family(prop):
    p = (prop or "").lower()
    for k in UNITMAP:
        if k in p:
            return k
    return None

def check(extracted, d):
    """Does the extracted declared unit agree with the registry reference flow?"""
    s = (extracted or "").lower().replace("\xa0", " ")
    fam = unit_family(d["property"])
    if not fam:
        return None
    unit_ok = any(re.search(rf"(?<![a-z]){re.escape(t)}(?![a-z])", s) for t in UNITMAP[fam])
    val = d["value"]
    val_ok = True
    if fam == "mass" and val:
        # 1000 kg == 1 t ; accept either rendering
        cands = {str(int(val)) if float(val).is_integer() else str(val)}
        if float(val) == 1000:
            cands |= {"1 t", "1t", "1 tonne", "1 ton", "1000 kg", "1,000 kg"}
        val_ok = any(c in s for c in cands)
    return unit_ok and val_ok

print("\n=== declared-unit agreement with the ILCD reference flow ===")
results = {}
for run, label in (("w1", "Gemini 2.5 Flash"), ("ds1", "DeepSeek V4-Flash"),
                   ("dp1", "DeepSeek V4-Pro")):
    ok = tot = skip = 0
    misses = []
    for u in core18:
        lp = os.path.join(CORPUS, u, f"llm_{run}.json")
        if not os.path.exists(lp):
            continue
        pj = json.load(open(os.path.join(CORPUS, u, "registry.json"), encoding="utf8"))
        d = ref_flow_property(pj)
        if not d:
            skip += 1; continue
        got = (json.load(open(lp, encoding="utf8")).get("declared_unit") or "").strip()
        r = check(got, d)
        if r is None:
            skip += 1; continue
        tot += 1; ok += bool(r)
        if not r:
            misses.append((d["property"], d["value"], d["unit"], got[:44]))
    if tot:
        print(f"  {label:20} {ok}/{tot} = {ok/tot*100:.1f}%   (skipped {skip})")
        results[run] = {"ok": ok, "tot": tot, "pct": ok / tot * 100}
        for m in misses[:4]:
            print(f"      miss: registry {m[0]} {m[1]} {m[2]} | extracted '{m[3]}'")

json.dump(results, open(os.path.join(ROOT, "declared_unit2.json"), "w"), indent=1)
print("\nwritten: data/declared_unit2.json")
