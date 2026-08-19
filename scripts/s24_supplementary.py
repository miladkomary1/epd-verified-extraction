"""Step 24: stage the supplementary material folder and corpus manifest CSV.

Includes: analysis scripts (s4-s23), result data JSONs, figures, corpus manifest.
Excludes: the 220 PDFs and registry JSONs (300+ MB; public data, re-fetchable with
the released collector), API keys (none are stored in any staged file).
"""
import json, os, shutil, csv

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
CORPUS = os.path.join(DATA, "corpus")
PAPER = os.path.join(ROOT, "..", "paper")
STAGE = os.path.join(ROOT, "..", "supplementary")

if os.path.exists(STAGE):
    shutil.rmtree(STAGE)
os.makedirs(os.path.join(STAGE, "scripts"))
os.makedirs(os.path.join(STAGE, "data"))
os.makedirs(os.path.join(STAGE, "figures"))

# ---- scripts (collector, ground truth, extraction, gates, scoring, figures) ----
SCRIPTS = ["s4_collect_corpus.py", "s4b_fix_pdfs.py", "s5_ground_truth.py",
           "s5b_sanity.py", "s5c_pair_screen.py", "s6_llm_extract.py",
           "s7_compare.py", "s8_grounding_gate.py", "s9_arith_gate_demo.py",
           "s9b_arith_check.py", "s10_collect_extended.py", "s12_ec3_cross.py",
           "s13_extract_w.py", "s14_score.py", "s15_det_parser.py",
           "s16_strict_schema.py", "s17_figures.py", "s18_aggregate.py",
           "s19_diag_ext.py", "s21_core_errs.py", "s23_ms_extra.py"]
for s in SCRIPTS:
    src = os.path.join(ROOT, s)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(STAGE, "scripts", s))

# ---- data (results only, no corpus documents) ----
DATA_FILES = ["stats.json", "ms_extra.json", "collect_stats.json", "pair_status.json",
              "strict_schema_outcome.json", "ec3_cross.json", "manifest.json"]
DATA_FILES += [f for f in os.listdir(DATA) if f.startswith(("eval_", "usage_", "score_"))]
for f in sorted(set(DATA_FILES)):
    src = os.path.join(DATA, f)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(STAGE, "data", f))

# ---- figures ----
for f in os.listdir(os.path.join(PAPER, "figures")):
    if f.endswith(".png"):
        shutil.copy2(os.path.join(PAPER, "figures", f), os.path.join(STAGE, "figures", f))

# ---- corpus manifest CSV ----
core18 = sorted(u for u in os.listdir(CORPUS)
                if os.path.exists(os.path.join(CORPUS, u, "llm_run1.json")))
pair = json.load(open(os.path.join(DATA, "pair_status.json")))
rows = []
for u in sorted(os.listdir(CORPUS)):
    gp = os.path.join(CORPUS, u, "gt.json")
    if not os.path.exists(gp):
        continue
    gt = json.load(open(gp, encoding="utf8"))
    ext_run = os.path.exists(os.path.join(CORPUS, u, "llm_wext.json"))
    rows.append({
        "registry_uuid": u,
        "product_name": gt["name"].strip(),
        "standard": gt.get("standard", ""),
        "reference_year": gt.get("ref_year", ""),
        "pdf_md5": gt.get("pdf_md5", ""),
        "pair_integrity": pair.get(u, ""),
        "corpus": "core" if u in core18 else ("extended" if ext_run else "collected_only"),
    })
with open(os.path.join(STAGE, "data", "corpus_manifest.csv"), "w", newline="", encoding="utf8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

n_files = sum(len(fs) for _, _, fs in os.walk(STAGE))
print(f"staged {n_files} files; corpus manifest rows: {len(rows)}")
print("core:", sum(1 for r in rows if r["corpus"] == "core"),
      "extended:", sum(1 for r in rows if r["corpus"] == "extended"),
      "collected_only:", sum(1 for r in rows if r["corpus"] == "collected_only"))
