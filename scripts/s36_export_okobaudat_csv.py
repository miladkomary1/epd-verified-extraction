# -*- coding: utf-8 -*-
"""Nikola's deliverable: one ÖKOBAUDAT-compatible CSV row per product, combining the
core indicator extraction (llm_w1 / llm_wext) with the datasheet extraction
(llm_meta1). A new EPD processed by the same pipeline appends one more row, which can
then be merged with an ÖKOBAUDAT export and fed into downstream software."""
import json, os, sys, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s14_score import norm_mod, load_llm

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")
OUT = os.path.join(ROOT, "okobaudat_compatible_export.csv")

CORE = ["GWP-total", "GWP-fossil", "GWP-biogenic", "GWP-luluc", "ODP", "AP",
        "EP-freshwater", "EP-marine", "EP-terrestrial", "POCP", "ADPE", "ADPF", "WDP",
        "PERE", "PERM", "PERT", "PENRE", "PENRM", "PENRT",
        "SM", "RSF", "NRSF", "FW", "HWD", "NHWD", "RWD"]
EXTRA = ["GWP-GHG", "PM", "IRP", "ETP-fw", "HTP-c", "HTP-nc", "SQP",
         "CRU", "MFR", "MER", "EEE", "EET"]
MODULES = ["A1", "A2", "A3", "A1-A3", "A4", "A5", "B1", "B2", "B3", "B4", "B5",
           "B6", "B7", "C1", "C2", "C3", "C4", "D"]

docs = sorted(u for u in os.listdir(CORPUS)
              if os.path.exists(os.path.join(CORPUS, u, "llm_" + (os.environ.get("META_RUN","meta_ds")) + ".json")))
rows = []
mod_used = set()
for u in docs:
    d = os.path.join(CORPUS, u)
    gt = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))
    meta = json.load(open(os.path.join(d, "llm_" + (os.environ.get("META_RUN","meta_ds")) + ".json"), encoding="utf8"))
    core_p = os.path.join(d, "llm_w1.json")
    if not os.path.exists(core_p):
        core_p = os.path.join(d, "llm_wext.json")
    core = load_llm(core_p)
    extra = {}
    for code, obj in (meta.get("indicators") or {}).items():
        if isinstance(obj, dict):
            raw = obj.get("values", obj)
            if isinstance(raw, dict):
                extra[code] = {norm_mod(k): v for k, v in raw.items()
                               if isinstance(v, (int, float))}
    row = {
        "source": "extracted_from_pdf",
        "registry_uuid": u,
        "product_name": gt["name"].strip(),
        "registration_number": meta.get("registration_number") or "",
        "program_operator": meta.get("program_operator") or "",
        "standard": meta.get("standard") or "",
        "issue_date": meta.get("issue_date") or "",
        "valid_until": meta.get("valid_until") or "",
        "geography": meta.get("geography") or "",
        "declared_unit": (json.load(open(core_p, encoding="utf8"))
                          .get("declared_unit") or ""),
    }
    for code in CORE + EXTRA:
        vals = core.get(code) or extra.get(code) or {}
        for m, v in vals.items():
            if m in MODULES:
                row[f"{code}_{m}"] = v
                mod_used.add((code, m))
    rows.append(row)

meta_cols = ["source", "registry_uuid", "product_name", "registration_number",
             "program_operator", "standard", "issue_date", "valid_until",
             "geography", "declared_unit"]
ind_cols = [f"{c}_{m}" for c in CORE + EXTRA for m in MODULES if (c, m) in mod_used]
with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=meta_cols + ind_cols, restval="")
    w.writeheader()
    w.writerows(rows)

print(f"written {OUT}")
print(f"  {len(rows)} products x {len(meta_cols) + len(ind_cols)} columns "
      f"({len(ind_cols)} indicator-module columns)")
filled = sum(1 for r in rows for c in ind_cols if r.get(c) not in (None, ""))
print(f"  indicator cells filled: {filled}")
