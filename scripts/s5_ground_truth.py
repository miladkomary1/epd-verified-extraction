"""Step 5: build flat ground-truth tables from registry.json for each corpus item.

Output per item: gt.json = {
  name, ref_year, valid_until, standard, declared_unit,
  indicators: { CODE: {unit, modules: {module: value}} }   # LCIA + LCI exchanges
}
"""
import json, os, re, hashlib

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")

CODE_RE = re.compile(r"\(([A-Za-z\-]+(?:-[a-z]+)?)\)\s*$")

def en(short):
    """pick english value from multilang list"""
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

def parse_amounts(anies):
    unit, modules = "", {}
    for a in anies:
        if not isinstance(a, dict):
            continue
        if a.get("name") == "referenceToUnitGroupDataSet":
            unit = en(a.get("value", {}).get("shortDescription"))
        elif "module" in a and "value" in a:
            try:
                modules[a["module"]] = float(a["value"])
            except (TypeError, ValueError):
                pass
    return unit, modules

def extract(pj):
    out = {}
    # LCIA results
    for x in pj.get("LCIAResults", {}).get("LCIAResult", []):
        nm = en(x.get("referenceToLCIAMethodDataSet", {}).get("shortDescription"))
        m = CODE_RE.search(nm.strip())
        code = m.group(1) if m else nm.strip()
        unit, modules = parse_amounts(x.get("other", {}).get("anies", []))
        if modules:
            out[code] = {"name": nm, "unit": unit, "modules": modules}
    # LCI exchanges (resource use / waste flows)
    for x in pj.get("exchanges", {}).get("exchange", []):
        nm = en(x.get("referenceToFlowDataSet", {}).get("shortDescription"))
        m = CODE_RE.search(nm.strip())
        code = m.group(1) if m else nm.strip()
        unit, modules = parse_amounts(x.get("other", {}).get("anies", []))
        if modules and code not in out:
            out[code] = {"name": nm, "unit": unit, "modules": modules}
    return out

def meta(pj):
    pi = pj.get("processInformation", {})
    dsi = pi.get("dataSetInformation", {})
    name = en(dsi.get("name", {}).get("baseName"))
    # declared unit: quantitativeReference -> functionalUnitOrOther
    qr = pi.get("quantitativeReference", {})
    du = en(qr.get("functionalUnitOrOther"))
    time_info = pi.get("time", {})
    ref_year = time_info.get("referenceYear")
    valid = time_info.get("dataSetValidUntil")
    # standard
    std = ""
    for c in pj.get("modellingAndValidation", {}).get("complianceDeclarations", {}).get("compliance", []):
        t = en(c.get("referenceToComplianceSystem", {}).get("shortDescription"))
        if "15804" in t:
            std = t
    return {"name": name, "declared_unit": du, "ref_year": ref_year, "valid_until": valid, "standard": std}

items = []
for uuid in sorted(os.listdir(CORPUS)):
    d = os.path.join(CORPUS, uuid)
    rj = os.path.join(d, "registry.json")
    if not os.path.exists(rj):
        continue
    pj = json.load(open(rj, encoding="utf8"))
    gt = meta(pj)
    gt["uuid"] = uuid
    gt["indicators"] = extract(pj)
    gt["pdf_md5"] = hashlib.md5(open(os.path.join(d, "epd.pdf"), "rb").read()).hexdigest()
    json.dump(gt, open(os.path.join(d, "gt.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    n_ind = len(gt["indicators"])
    n_vals = sum(len(v["modules"]) for v in gt["indicators"].values())
    items.append((uuid, gt["name"], gt["standard"][:22], n_ind, n_vals, gt["pdf_md5"][:8]))

print(f"{'uuid':38.36} {'name':32.30} {'std':22} ind vals pdf")
for it in items:
    print(f"{it[0]:38.36} {it[1]:32.30} {it[2]:22} {it[3]:3} {it[4]:4} {it[5]}")
print("\nunique PDFs:", len({it[5] for it in items}), "of", len(items))
