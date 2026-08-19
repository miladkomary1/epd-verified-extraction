# -*- coding: utf-8 -*-
"""Aggregate the new results (full-stock scan, DeepSeek ext, datasheet verify,
model robustness) into data/stats2.json for manuscript v9."""
import json, os, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s14_score import score_run

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
S = {}

# ---- full-stock scan ----
p = os.path.join(ROOT, "fullstock_scan.jsonl")
if os.path.exists(p):
    rows = [json.loads(l) for l in open(p, encoding="utf8")]
    c = Counter(r["status"] for r in rows)
    n_spec = sum(v for k, v in c.items() if k != "generic")
    md5s = [r.get("pdf_md5") for r in rows if r.get("pdf_md5")]
    S["fullstock"] = {
        "total_records": len(rows),
        "generic": c.get("generic", 0),
        "specific": n_spec,
        "status": dict(c),
        "unique_pdfs": len(set(md5s)),
        "spec_no_pdf_source": c.get("no_pdf_source", 0),
        "spec_pdf_fetch_fail": c.get("pdf_fetch_fail", 0),
        "spec_no_text_layer": c.get("no_text_layer", 0),
        "spec_pair_ok": c.get("pair_ok", 0),
        "spec_pair_partial": c.get("pair_partial", 0),
        "spec_pair_mismatch": c.get("pair_mismatch", 0),
        "spec_no_anchor_values": c.get("no_anchor_values", 0),
    }
    f = S["fullstock"]
    denom_doccheck = (f["spec_pair_ok"] + f["spec_pair_partial"] + f["spec_pair_mismatch"])
    f["pct_no_pdf_of_specific"] = round(f["spec_no_pdf_source"] / max(n_spec, 1) * 100, 1)
    f["pct_mismatch_of_checked"] = round(f["spec_pair_mismatch"] / max(denom_doccheck, 1) * 100, 1)
    f["pct_partial_of_checked"] = round(f["spec_pair_partial"] / max(denom_doccheck, 1) * 100, 1)

# ---- DeepSeek extended ----
try:
    S["dsext"] = score_run("dsext", "ext")
    S["dsext"].pop("per_item", None)
    S["dsext"]["errors"] = S["dsext"]["errors"][:20]
    S["dsext"].pop("gated_errors", None)
except Exception as e:
    print("dsext scoring skipped:", repr(e)[:80])

# ---- model robustness summary (core) ----
S["robustness_core"] = {}
for run, label in (("w1", "gemini-2.5-flash"), ("ds1", "deepseek-v4-flash"),
                   ("dp1", "deepseek-v4-pro")):
    try:
        r = score_run(run, "core")
        S["robustness_core"][label] = {k: r[k] for k in
            ("coverage_pct", "precision_pct", "n_errors",
             "gated_coverage_pct", "gated_precision_pct", "gated_errors_surfaced")}
    except Exception:
        pass

# ---- datasheet ----
p = os.path.join(ROOT, "datasheet_verify.json")
if os.path.exists(p):
    S["datasheet"] = json.load(open(p))

# ---- cascade + declared unit (already computed) ----
for f, k in (("cascade.json", "cascade"), ("declared_unit2.json", "declared_unit")):
    p = os.path.join(ROOT, f)
    if os.path.exists(p):
        S[k] = json.load(open(p))

json.dump(S, open(os.path.join(ROOT, "stats2.json"), "w"), indent=1)
print(json.dumps({k: (v if not isinstance(v, dict) else "...") for k, v in S.items()},
                 indent=1))
if "fullstock" in S:
    print("\nfullstock:", json.dumps(S["fullstock"], indent=1))
if "dsext" in S:
    d = S["dsext"]
    print(f"\ndsext: cov={d['coverage_pct']:.1f} prec={d['precision_pct']:.2f} "
          f"gated={d['gated_precision_pct']:.2f} errSurf={d['gated_errors_surfaced']}")
