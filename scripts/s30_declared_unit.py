# -*- coding: utf-8 -*-
"""Comment 123: the declared unit is extracted but never evaluated.

Builds a declared-unit ground truth from the ILCD record (reference-flow amount +
functional unit flow properties) and scores the extraction for every model run.
"""
import json, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")

def en(short):
    if isinstance(short, list):
        for x in short:
            if isinstance(x, dict) and x.get("lang") == "en":
                return x.get("value", "")
        for x in short:
            if isinstance(x, dict):
                return x.get("value", "")
    if isinstance(short, dict):
        return short.get("value", "")
    return str(short or "")

def registry_declared_unit(pj):
    """Reference-flow amount and its flow properties, i.e. the declared unit."""
    dsi = pj["processInformation"]["dataSetInformation"]
    fu = en(dsi.get("name", {}).get("functionalUnitFlowProperties"))
    # reference flow: exchange with referenceFlow true
    amount, flow = None, ""
    for e in pj.get("exchanges", {}).get("exchange", []):
        if e.get("referenceFlow"):
            amount = e.get("meanAmount")
            flow = en(e.get("referenceToFlowDataSet", {}).get("shortDescription"))
            break
    return {"functional_unit_props": fu, "ref_flow_amount": amount, "ref_flow_name": flow}

# ---- inspect what the registry actually gives us ----
print("=== registry declared-unit fields (first 6) ===")
core18 = sorted(u for u in os.listdir(CORPUS)
                if os.path.exists(os.path.join(CORPUS, u, "llm_run1.json")))
for u in core18[:6]:
    pj = json.load(open(os.path.join(CORPUS, u, "registry.json"), encoding="utf8"))
    d = registry_declared_unit(pj)
    print(f"  amount={d['ref_flow_amount']}  props='{d['functional_unit_props'][:46]}'")

# ---- scoring ----
UNIT_ALIASES = {"m2": "m²", "m3": "m³", "m^2": "m²", "m^3": "m³",
                "qm": "m²", "stk": "piece", "stück": "piece", "st": "piece",
                "tonne": "t", "ton": "t", "kilogram": "kg", "metre": "m", "meter": "m"}

def norm_unit(s):
    s = (s or "").lower().strip()
    s = s.replace("\xa0", " ")
    s = re.sub(r"[()\[\],;:]", " ", s)
    s = re.sub(r"\s+", " ", s)
    for k, v in UNIT_ALIASES.items():
        s = re.sub(rf"\b{re.escape(k)}\b", v, s)
    return s

def unit_core(s):
    """Extract the leading quantity+unit, e.g. '1 m²' from '1 m² ADAGIO HD+ ...'."""
    s = norm_unit(s)
    m = re.match(r"^\s*([\d.,]+)\s*([a-zà-ÿ²³µ/·%\.]+)", s)
    if m:
        return f"{m.group(1).replace(',', '.').rstrip('.0') or '1'} {m.group(2)}"
    return s[:24]

def score(run):
    ok = tot = 0
    misses = []
    for u in core18:
        d = os.path.join(CORPUS, u)
        lp = os.path.join(d, f"llm_{run}.json")
        if not os.path.exists(lp):
            continue
        pj = json.load(open(os.path.join(d, "registry.json"), encoding="utf8"))
        reg = registry_declared_unit(pj)
        got = (json.load(open(lp, encoding="utf8")).get("declared_unit") or "").strip()
        tot += 1
        amt = reg["ref_flow_amount"]
        # agreement: the extracted string must contain the reference-flow amount and
        # its unit must match the registry's functional-unit properties
        gu = unit_core(reg["functional_unit_props"]) if reg["functional_unit_props"] else ""
        lu = unit_core(got)
        amt_ok = amt is not None and (
            re.search(rf"(?<!\d){re.sub(r'\.0$', '', str(amt))}(?!\d)", got) is not None)
        unit_ok = bool(gu) and (gu.split()[-1] in lu or lu.split()[-1] in gu) if gu and lu else False
        good = amt_ok and (unit_ok or not gu)
        ok += good
        if not good:
            misses.append((u[:8], reg["functional_unit_props"][:30], got[:40], amt))
    return ok, tot, misses

print("\n=== declared-unit agreement with the registry ===")
for run, label in (("w1", "Gemini 2.5 Flash"), ("ds1", "DeepSeek V4-Flash"),
                   ("dp1", "DeepSeek V4-Pro")):
    if not os.path.exists(os.path.join(CORPUS, core18[0], f"llm_{run}.json")):
        continue
    ok, tot, misses = score(run)
    print(f"  {label:20} {ok}/{tot} = {ok/tot*100:.1f}%")
    for m in misses[:4]:
        print(f"      miss {m[0]}: registry='{m[1]}' amount={m[3]} | extracted='{m[2]}'")

# extended corpus coverage (extraction present at all)
ext = [u for u in os.listdir(CORPUS) if os.path.exists(os.path.join(CORPUS, u, "llm_wext.json"))]
n_du = sum(1 for u in ext
           if (json.load(open(os.path.join(CORPUS, u, "llm_wext.json"), encoding="utf8"))
               .get("declared_unit") or "").strip())
print(f"\nextended corpus: declared unit returned for {n_du}/{len(ext)} documents")

json.dump({"core_n": len(core18), "ext_n": len(ext), "ext_returned": n_du},
          open(os.path.join(ROOT, "declared_unit.json"), "w"), indent=1)
