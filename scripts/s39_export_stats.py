# -*- coding: utf-8 -*-
"""Re-run the registry-layout export and capture its statistics as JSON, so the
manuscript build reads numbers from data instead of from a message.

Also records the structural facts of the published OEKOBAUDAT export that the
paper states (delimiter, encoding, column count, the two amendment column sets,
the SOP/SQP naming divergence, year-granularity validity fields).
"""
import csv, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(DATA, "okobaudat_real_stats.json")
GEN = os.path.join(DATA, "okobaudat_real_export.csv")
REF = os.path.join(DATA, "okobaudat_reference.csv")

r = subprocess.run([sys.executable, os.path.join(HERE, "s37_export_okobaudat_real.py")],
                   capture_output=True, text=True, cwd=HERE)
log = r.stdout + r.stderr
print(log.strip())


def grab(pattern, cast=int):
    m = re.search(pattern, log)
    return cast(m.group(1)) if m else None


stats = {
    "products_with_rows": grab(r"products:\s*(\d+)"),
    "rows": grab(r"rows:\s*(\d+)"),
    "columns": grab(r"columns:\s*(\d+)"),
    "values_written": grab(r"values written:\s*(\d+)"),
    "values_withheld": grab(r"withheld by the checks:\s*(\d+)"),
    "products_nothing_verified": grab(r"products with nothing verified \(no rows\):\s*(\d+)") or 0,
}

with open(GEN, newline="", encoding="iso-8859-1") as f:
    gen = list(csv.reader(f, delimiter=";"))
with open(REF, newline="", encoding="iso-8859-1") as f:
    ref = list(csv.reader(f, delimiter=";"))

hdr = ref[0]
stats["products_total"] = stats["products_with_rows"] + stats["products_nothing_verified"]
stats["header_matches_published_export"] = (hdr == gen[0])
stats["rows_check"] = len(gen) - 1

# structural facts of the published layout, read from the published header itself
a2_cols = [c for c in hdr if c.endswith("(A2)")]
a1_cols = ["GWP", "ODP", "POCP", "AP", "EP", "ADPE", "ADPF"]
stats["format"] = {
    "delimiter": "semicolon",
    "encoding": "ISO-8859-1",
    "line_ending": "CRLF",
    "columns": len(hdr),
    "row_granularity": "one row per product and life-cycle module",
    "module_column": "Modul",
    "module_column_index": hdr.index("Modul"),
    "a2_impact_columns": len(a2_cols),
    "a1_impact_columns": sum(1 for c in a1_cols if c in hdr),
    "soil_quality_column_name": next((c for c in hdr if "SOP" in c or "SQP" in c), None),
    "validity_fields_are_years": True,
    "validity_field_names": ["Referenzjahr", "Gueltig bis"],
    "validity_sample_values": [r[hdr.index("Referenzjahr")] for r in ref[1:]]
                              + [r[hdr.index("Gueltig bis")] for r in ref[1:]],
    "unit_field_name": "Bezugseinheit",
    "unit_sample_values": [r[hdr.index("Bezugseinheit")] for r in ref[1:]],
}

# Scenario-split modules: the declarations print module codes such as C3/1 or D/2
# when a module carries several end-of-life scenarios. The export currently keeps the
# split inside the module code and leaves the registry's own Szenario column empty.
mi, si = hdr.index("Modul"), hdr.index("Szenario")
split_rows = [r for r in gen[1:] if "/" in r[mi]]
stats["scenario_split"] = {
    "rows_with_split_module": len(split_rows),
    "pct_of_rows": round(100 * len(split_rows) / (len(gen) - 1), 1),
    "distinct_split_codes": sorted({r[mi] for r in split_rows}),
    "szenario_column_populated": sum(1 for r in gen[1:] if r[si].strip()),
}

json.dump(stats, open(OUT, "w", encoding="utf8"), indent=1, ensure_ascii=False)
print("\nwritten:", OUT)
print(json.dumps(stats, indent=1, ensure_ascii=False))
