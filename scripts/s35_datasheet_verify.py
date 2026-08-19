# -*- coding: utf-8 -*-
"""Verify the datasheet extraction (llm_meta1.json) against the registry ILCD record:
metadata fields + the 12 additional indicator codes, scored with the same tolerance
harness as the main study."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s14_score import norm_mod, matches, load_llm

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")
COUNTRY = {
 "US": ["US", "USA", "UNITED STATES"], "GB": ["GB", "UK", "UNITED KINGDOM"],
 "DE": ["DE", "GERMANY", "DEUTSCHLAND"], "CH": ["CH", "SWITZERLAND", "SCHWEIZ"],
 "AT": ["AT", "AUSTRIA"], "BE": ["BE", "BELGIUM"], "FR": ["FR", "FRANCE"],
 "IT": ["IT", "ITALY"], "ES": ["ES", "SPAIN"], "NL": ["NL", "NETHERLANDS"],
 "PL": ["PL", "POLAND"], "SE": ["SE", "SWEDEN"], "DK": ["DK", "DENMARK"],
 "NO": ["NO", "NORWAY"], "FI": ["FI", "FINLAND"], "CZ": ["CZ", "CZECH"],
 "MX": ["MX", "MEXICO"], "CN": ["CN", "CHINA"], "IE": ["IE", "IRELAND"],
 "PT": ["PT", "PORTUGAL"], "TR": ["TR", "TURKEY", "TURKIYE"], "GR": ["GR", "GREECE"],
 "HU": ["HU", "HUNGARY"], "RO": ["RO", "ROMANIA"], "SK": ["SK", "SLOVAKIA"],
 "SI": ["SI", "SLOVENIA"], "HR": ["HR", "CROATIA"], "LU": ["LU", "LUXEMBOURG"],
 "RER": ["RER", "EUROPE", "EUROPEAN", "EU", "EUROPA"],
 "GLO": ["GLO", "GLOBAL", "WORLD", "WELT"],
}
EXTRA = ["GWP-GHG", "PM", "IRP", "ETP-fw", "HTP-c", "HTP-nc", "SQP",
         "CRU", "MFR", "MER", "EEE", "EET"]

def en(sd):
    if isinstance(sd, list):
        for x in sd:
            if isinstance(x, dict) and x.get("lang") == "en":
                return x.get("value", "")
        for x in sd:
            if isinstance(x, dict):
                return x.get("value", "")
    return str(sd or "")

def registry_meta(pj):
    pi = pj.get("processInformation", {})
    t = pi.get("time", {})
    geo = (pi.get("geography", {}).get("locationOfOperationSupplyOrProduction", {})
           .get("location"))
    std = ""
    for c in (pj.get("modellingAndValidation", {}).get("complianceDeclarations", {})
              .get("compliance", [])):
        s = en(c.get("referenceToComplianceSystem", {}).get("shortDescription"))
        if "15804" in s:
            std = s
    reg_no = (pj.get("administrativeInformation", {}).get("publicationAndOwnership", {})
              .get("registrationNumber"))
    return {"ref_year": t.get("referenceYear"), "valid_until": t.get("dataSetValidUntil"),
            "geography": geo, "standard": std, "registration_number": reg_no}

def registry_extra_indicators(pj):
    out = {}
    for x in pj.get("LCIAResults", {}).get("LCIAResult", []):
        nm = en(x.get("referenceToLCIAMethodDataSet", {}).get("shortDescription"))
        m = re.search(r"\(([A-Za-z\-]+(?:-[a-z]+)?)\)\s*$", nm.strip())
        code = m.group(1) if m else None
        if code not in EXTRA:
            continue
        mods = {}
        for a in x.get("other", {}).get("anies", []):
            if isinstance(a, dict) and "module" in a and "value" in a:
                try:
                    mods[norm_mod(a["module"])] = float(a["value"])
                except (TypeError, ValueError):
                    pass
        if mods:
            out[code] = mods
    for x in pj.get("exchanges", {}).get("exchange", []):
        nm = en(x.get("referenceToFlowDataSet", {}).get("shortDescription"))
        m = re.search(r"\(([A-Za-z\-]+)\)\s*$", nm.strip())
        code = m.group(1) if m else None
        if code not in EXTRA or code in out:
            continue
        mods = {}
        for a in x.get("other", {}).get("anies", []):
            if isinstance(a, dict) and "module" in a and "value" in a:
                try:
                    mods[norm_mod(a["module"])] = float(a["value"])
                except (TypeError, ValueError):
                    pass
        if mods:
            out[code] = mods
    return out

docs = sorted(u for u in os.listdir(CORPUS)
              if os.path.exists(os.path.join(CORPUS, u, "llm_" + (os.environ.get("META_RUN","meta_ds")) + ".json")))
S = {"docs": len(docs),
     "valid_until": [0, 0], "geography": [0, 0], "standard": [0, 0],
     "registration_number": [0, 0], "reg_no_registry_missing": 0,
     "geo_semantic_diff": 0, "geo_true_miss": 0,
     "ind_slots": 0, "ind_pop": 0, "ind_ok": 0}
misses = {"valid_until": [], "geography": [], "standard": []}

for u in docs:
    d = os.path.join(CORPUS, u)
    pj = json.load(open(os.path.join(d, "registry.json"), encoding="utf8"))
    reg = registry_meta(pj)
    ex = json.load(open(os.path.join(d, "llm_" + (os.environ.get("META_RUN","meta_ds")) + ".json"), encoding="utf8"))
    # valid_until: registry stores a year
    if reg["valid_until"]:
        S["valid_until"][1] += 1
        got = str(ex.get("valid_until") or "")
        if str(reg["valid_until"]) in got:
            S["valid_until"][0] += 1
        else:
            misses["valid_until"].append((reg["valid_until"], got[:24]))
    # geography: three-way classification
    if reg["geography"]:
        S["geography"][1] += 1
        got = (ex.get("geography") or "").strip()
        r = reg["geography"].upper()
        aliases = COUNTRY.get(r, [r])
        gu = got.upper()
        ok = any(re.search(rf"\b{re.escape(a)}\b", gu) for a in aliases)
        if ok:
            S["geography"][0] += 1
        else:
            text = open(os.path.join(d, "pdftext.txt"), encoding="utf8").read().upper()
            in_doc = any(re.search(rf"\b{re.escape(a)}\b", text) for a in aliases)
            if not in_doc:
                S["geo_semantic_diff"] += 1        # registry scope not stated in document
            else:
                S["geo_true_miss"] += 1
                misses["geography"].append((r, got[:24]))

    # standard
    if reg["standard"]:
        S["standard"][1] += 1
        got = (ex.get("standard") or "").upper().replace(" ", "")
        ok = "A2" in got if "A2" in reg["standard"].upper() else "15804" in got
        S["standard"][0] += ok
        if not ok:
            misses["standard"].append((reg["standard"][:24], got[:24]))
    # registration number: registry rarely stores it
    if reg["registration_number"]:
        S["registration_number"][1] += 1
        if str(reg["registration_number"]).replace("-", "").upper() in \
           str(ex.get("registration_number") or "").replace("-", "").upper():
            S["registration_number"][0] += 1
    else:
        S["reg_no_registry_missing"] += 1
    # extra indicators
    rex = registry_extra_indicators(pj)
    lex = {}
    for code, obj in (ex.get("indicators") or {}).items():
        if isinstance(obj, dict):
            raw = obj.get("values", obj)
            if isinstance(raw, dict):
                lex[code] = {norm_mod(k): float(v) for k, v in raw.items()
                             if isinstance(v, (int, float))}
    for code, mods in rex.items():
        for m, gv in mods.items():
            S["ind_slots"] += 1
            lv = lex.get(code, {}).get(m)
            if lv is not None:
                S["ind_pop"] += 1
                S["ind_ok"] += matches(lv, gv)

print(f"docs with datasheet extraction: {S['docs']}")
for k in ("valid_until", "geography", "standard", "registration_number"):
    ok, tot = S[k]
    print(f"  {k:20} {ok}/{tot}" + (f" = {ok/tot*100:.1f}%" if tot else "  (registry has none)"))
print(f"  reg-number absent from registry for {S['reg_no_registry_missing']} docs")
print(f"  geography: {S['geography'][0]} agree, {S['geo_semantic_diff']} registry scope "
      f"not stated in the document (semantic difference), {S['geo_true_miss']} true misses")
print(f"\nadditional indicators: {S['ind_slots']} registry slots, "
      f"populated {S['ind_pop']} ({S['ind_pop']/max(S['ind_slots'],1)*100:.1f}%), "
      f"agreeing {S['ind_ok']} ({S['ind_ok']/max(S['ind_pop'],1)*100:.2f}% of populated)")
for k, v in misses.items():
    if v:
        print(f"  sample {k} misses:", v[:4])

json.dump(S, open(os.path.join(ROOT, "datasheet_verify.json"), "w"), indent=1)
print("\nwritten: data/datasheet_verify.json")
