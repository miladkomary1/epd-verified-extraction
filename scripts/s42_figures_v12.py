# -*- coding: utf-8 -*-
"""New manuscript figures from the registry-wide scan, cross-model runs and datasheet
verification. Writes to paper/figures/ at 400 dpi."""
import json, os
from collections import Counter, defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
FIGD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "paper", "figures")
plt.rcParams.update({"font.size": 9, "font.family": "Arial"})

S2 = json.load(open(os.path.join(ROOT, "stats2.json")))
RC = json.load(open(os.path.join(ROOT, "integrity_recheck.json")))
CH = json.load(open(os.path.join(ROOT, "round2_checks.json")))
F = S2["fullstock"]
rows = [json.loads(l) for l in open(os.path.join(ROOT, "fullstock_scan.jsonl"), encoding="utf8")]

BLUE, DBLUE, RED, GREY, GREEN = "#7fa8d0", "#2b5c8a", "#c0392b", "#b0b0b0", "#2b8a4a"

# ---------------- Figure 5: registry-wide integrity ----------------
fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.1), gridspec_kw={"width_ratios": [1.15, 1]})

ax = axes[0]
stages = [("process records in stock", F["total_records"]),
          ("manufacturer-specific", F["specific"]),
          ("with retrievable document", F["specific"] - F["spec_no_pdf_source"]
           - F["spec_pdf_fetch_fail"]),
          ("screened against own values", RC["records_checked"]),
          ("unique documents behind them", RC["unique_documents"])]
ypos = list(range(len(stages)))[::-1]
cols = [BLUE, BLUE, BLUE, DBLUE, GREY]
ax.barh(ypos, [s[1] for s in stages], color=cols, height=0.62)
for yi, (lab, v) in zip(ypos, stages):
    ax.text(v + 55, yi, f"{v:,}", va="center", fontsize=8, color="#123")
ax.set_yticks(ypos); ax.set_yticklabels([s[0] for s in stages], fontsize=7.8)
ax.set_xlim(0, F["total_records"] * 1.2); ax.set_xlabel("records")
ax.set_title("(a) Registry-wide screen", fontsize=9)
ax.spines[["top", "right"]].set_visible(False)

ax = axes[1]
rec = [RC["records_checked"] - int(F["spec_pair_mismatch"]) - int(F["spec_pair_partial"]),
       int(F["spec_pair_partial"]), int(F["spec_pair_mismatch"])]
doc = [RC["doc_status"].get("ok", 0), RC["doc_status"].get("partial", 0),
       RC["doc_status"].get("all_mismatch", 0) + RC["doc_status"].get("mixed", 0)]
labels = ["per record\n(n=%d)" % RC["records_checked"], "per document\n(n=%d)" % RC["unique_documents"]]
full = [rec[0] / sum(rec) * 100, doc[0] / sum(doc) * 100]
part = [rec[1] / sum(rec) * 100, doc[1] / sum(doc) * 100]
mism = [rec[2] / sum(rec) * 100, doc[2] / sum(doc) * 100]
ax.bar(labels, full, color=GREEN, label="traceable")
ax.bar(labels, part, bottom=full, color="#e8b04b", label="partly traceable")
ax.bar(labels, mism, bottom=[f + p for f, p in zip(full, part)], color=RED,
       label="not traceable")
for i in range(2):
    ax.text(i, full[i] + part[i] + mism[i] + 1.5, f"{mism[i]:.1f}% not traceable",
            ha="center", fontsize=8, color=RED)
ax.set_ylabel("% of units"); ax.set_ylim(0, 118)
ax.legend(fontsize=7.5, loc="lower center", ncol=3, frameon=False,
          bbox_to_anchor=(0.5, -0.32))
ax.set_title("(b) Failure rate by denominator", fontsize=9)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig(os.path.join(FIGD, "fig5_registry_integrity.png"), dpi=400, bbox_inches="tight")
plt.close()

# ---------------- Figure 6: no-document rate by product family ----------------
EN = [("Komponenten", "Window and facade components"),
      ("Metalle", "Metals"),
      ("Komposite", "Composites"),
      ("Kunststoffe", "Plastics"),
      ("Beschichtungen", "Coatings"),
      ("Geb", "Building services"),
      ("D\u00e4mm", "Insulation"),
      ("Damm", "Insulation"),
      ("Holz", "Wood"),
      ("Mineralische", "Mineral construction products")]

def en_name(c):
    for k, v in EN:
        if c.startswith(k):
            return v
    return c

cat = [(en_name(c), n, tot, p) for c, n, tot, p in CH["cat_table"]]
cat.sort(key=lambda x: x[3])
fig, ax = plt.subplots(figsize=(6.6, 3.2))
y = range(len(cat))
bars = ax.barh(list(y), [c[3] for c in cat], color=BLUE, height=0.66)
overall = F["pct_no_pdf_of_specific"]
ax.axvline(overall, color=RED, ls="--", lw=1.2)
ax.text(overall + 1, len(cat) - 0.4, f"overall {overall}%", color=RED, fontsize=8)
for i, (name, n, tot, p) in enumerate(cat):
    ax.text(p + 1, i, f"{p:.1f}%  ({n}/{tot})", va="center", fontsize=7.6, color="#123")
ax.set_yticks(list(y)); ax.set_yticklabels([c[0] for c in cat], fontsize=8)
ax.set_xlim(0, 70); ax.set_xlabel("manufacturer-specific records with no retrievable document (%)")
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig(os.path.join(FIGD, "fig6_no_document_by_family.png"), dpi=400, bbox_inches="tight")
plt.close()

# ---------------- Figure S1 (supplementary): cross-model robustness ----------
R = S2["robustness_core"]
fig, ax = plt.subplots(figsize=(6.4, 3.2))
names = [("gemini-2.5-flash", "Gemini 2.5 Flash\n(10 runs)"),
         ("deepseek-v4-flash", "DeepSeek V4-Flash\n(1 run)"),
         ("deepseek-v4-pro", "DeepSeek V4-Pro\n(1 run)")]
x = range(len(names))
cov = [R[k]["coverage_pct"] for k, _ in names]
gcov = [R[k]["gated_coverage_pct"] for k, _ in names]
agr = [R[k]["precision_pct"] for k, _ in names]
gagr = [R[k]["gated_precision_pct"] for k, _ in names]
w = 0.2
ax.bar([i - 1.5 * w for i in x], cov, w, color=BLUE, label="coverage, before checks")
ax.bar([i - 0.5 * w for i in x], gcov, w, color=DBLUE, label="coverage, after checks")
ax.bar([i + 0.5 * w for i in x], agr, w, color="#e8b04b", label="agreement, before checks")
ax.bar([i + 1.5 * w for i in x], gagr, w, color=GREEN, label="agreement, after checks")
for i in x:
    ax.text(i + 1.5 * w, gagr[i] + 1.0, f"{gagr[i]:.2f}", ha="center", fontsize=7.5,
            color=GREEN)
ax.set_xticks(list(x)); ax.set_xticklabels([n for _, n in names], fontsize=8)
ax.set_ylim(0, 116); ax.set_ylabel("%")
ax.legend(fontsize=7.4, ncol=2, frameon=False, loc="lower center",
          bbox_to_anchor=(0.5, -0.42))
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig(os.path.join(FIGD, "figS1_cross_model.png"), dpi=400, bbox_inches="tight")
plt.close()

print("written:")
for f in ("fig5_registry_integrity.png", "fig6_no_document_by_family.png",
          "figS1_cross_model.png"):
    p = os.path.join(FIGD, f)
    print(f"  {f}  {os.path.getsize(p)//1024} KB")
