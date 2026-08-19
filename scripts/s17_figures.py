"""Step 17: manuscript figures (PNG, 300 dpi) from data/stats.json -> paper/figures/."""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
FIGD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "paper", "figures")
os.makedirs(FIGD, exist_ok=True)
S = json.load(open(os.path.join(ROOT, "stats.json")))
plt.rcParams.update({"font.size": 9, "font.family": "Arial"})

# ---------- Fig 1: workflow diagram ----------
fig, ax = plt.subplots(figsize=(7.0, 3.4))
ax.axis("off")
def box(x, y, w, h, label, fc="#eef3fa", ec="#2b5c8a"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012",
                                fc=fc, ec=ec, lw=1.2))
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=8.2)
def arrow(x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 mutation_scale=11, color="#444", lw=1.1))
box(0.01, 0.62, 0.14, 0.24, "PDF EPD\n(registry or\nprogram website)")
box(0.20, 0.62, 0.16, 0.24, "Text extraction &\nUnicode normalisation")
box(0.41, 0.62, 0.19, 0.24, "LLM extraction\n(components + totals,\nschema-less JSON)")
box(0.41, 0.18, 0.19, 0.24, "Deterministic\ntable parser\n(free path)", fc="#eefaf0", ec="#2b8a4a")
box(0.65, 0.62, 0.15, 0.24, "Source-grounding\ngate (locatability)")
box(0.65, 0.18, 0.15, 0.24, "Arithmetic gate\n(EN 15804 identities)")
box(0.85, 0.40, 0.14, 0.24, "Verified\nmachine-readable\nrecord")
arrow(0.15, 0.74, 0.20, 0.74)
arrow(0.36, 0.74, 0.41, 0.74)
arrow(0.28, 0.62, 0.41, 0.34)
arrow(0.60, 0.74, 0.65, 0.74)
arrow(0.725, 0.62, 0.725, 0.42)
arrow(0.80, 0.30, 0.85, 0.44)
arrow(0.80, 0.74, 0.885, 0.64)
arrow(0.60, 0.30, 0.65, 0.30)
ax.text(0.5, 0.02, "Evaluation: label-free comparison with registry digital records "
                   "(ÖKOBAUDAT ILCD; EC3 cross-check)", ha="center", fontsize=8,
        style="italic", color="#555")
plt.tight_layout()
plt.savefig(os.path.join(FIGD, "fig1_workflow.png"), dpi=400, bbox_inches="tight")
plt.close()

# ---------- Fig 2: main comparison ----------
w = S["core_w"]["agg"]; n = S["core_naive"]["agg"]; det = S["det_core"]
labels = ["Deterministic\nparser", "LLM naive\n(totals only)", "LLM workflow\n(ungated)", "Full workflow\n(gated)"]
cov = [det["coverage_pct"], n["coverage_pct"]["mean"], w["coverage_pct"]["mean"], w["gated_coverage_pct"]["mean"]]
cov_e = [0, n["coverage_pct"]["ci"], w["coverage_pct"]["ci"], w["gated_coverage_pct"]["ci"]]
prec = [det["precision_pct"], n["precision_pct"]["mean"], w["precision_pct"]["mean"], w["gated_precision_pct"]["mean"]]
prec_e = [0, n["precision_pct"]["ci"], w["precision_pct"]["ci"], w["gated_precision_pct"]["ci"]]
x = range(len(labels))
fig, ax = plt.subplots(figsize=(6.6, 3.2))
b1 = ax.bar([i - 0.19 for i in x], cov, 0.38, yerr=cov_e, capsize=3,
            color="#7fa8d0", label="Coverage of registry slots (%)")
b2 = ax.bar([i + 0.19 for i in x], prec, 0.38, yerr=prec_e, capsize=3,
            color="#2b5c8a", label="Registry agreement on populated values (%)")
for i, (c, p) in enumerate(zip(cov, prec)):
    ax.text(i - 0.19, c + 1.2, f"{c:.1f}", ha="center", fontsize=7.5)
    ax.text(i + 0.19, p + 1.2, f"{p:.2f}", ha="center", fontsize=7.5)
ax.set_xticks(list(x)); ax.set_xticklabels(labels)
ax.set_ylim(0, 112); ax.set_ylabel("%")
ax.legend(loc="lower right", fontsize=8)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig(os.path.join(FIGD, "fig2_comparison.png"), dpi=400, bbox_inches="tight")
plt.close()

# ---------- Fig 3: gate effect (two panels) ----------
runs = S["core_w"]["runs"]
import statistics
def mci(k):
    vals = [r[k] for r in runs]
    m = sum(vals) / len(vals)
    if len(vals) < 2:
        return m, 0
    sd = statistics.stdev(vals)
    return m, 2.262 * sd / (len(vals) ** 0.5)
mean = lambda k: sum(r[k] for r in runs) / len(runs)
slots = runs[0]["gt_slots"]
raw_ok = mean("recall_pct") * slots / 100
raw_err = mean("n_errors")
g_ok = mean("gated_precision_pct") * mean("gated_coverage_pct") * slots / 1e4
g_err = mean("gated_errors_surfaced")
held_ok = mean("correct_withheld"); held_err = mean("errors_withheld")

fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9), gridspec_kw={"width_ratios": [1.35, 1]})
ax = axes[0]
cats = ["LLM output\n(before gates)", "Surfaced after\ngates"]
ax.barh(cats, [raw_ok, g_ok], color="#2b8a4a", label="registry-agreeing values")
ax.barh(cats, [raw_err, g_err], left=[raw_ok, g_ok], color="#c0392b", label="registry-disagreeing values")
ax.barh(cats[1], held_ok + held_err, left=g_ok + g_err, color="#cccccc", label="withheld by gates")
ax.set_xlabel(f"field-slots (of {slots} registry slots)")
ax.legend(loc="lower right", fontsize=7.5)
ax.set_title("(a) Output composition", fontsize=9)
ax.spines[["top", "right"]].set_visible(False)

ax = axes[1]
labels = ["disagreeing\nbefore gates", "disagreeing\nsurfaced after", "agreeing\nwithheld"]
means, cis = [], []
for k in ("n_errors", "gated_errors_surfaced", "correct_withheld"):
    m, ci = mci(k); means.append(m); cis.append(ci)
bars = ax.bar(labels, means, yerr=cis, capsize=4,
              color=["#c0392b", "#2b8a4a", "#999999"], width=0.55)
for b, m in zip(bars, means):
    ax.text(b.get_x() + b.get_width() / 2, m + 0.9, f"{m:.1f}", ha="center", fontsize=8)
ax.set_ylabel("values per run")
ax.set_title("(b) Disagreeing and withheld values", fontsize=9)
ax.set_ylim(0, max(means) * 1.25 + 1)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig(os.path.join(FIGD, "fig3_gates.png"), dpi=400, bbox_inches="tight")
plt.close()

# ---------- Fig 4: extended corpus ----------
if "ext_w" in S:
    e = S["ext_w"]
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.1),
                             gridspec_kw={"width_ratios": [1.25, 1]})
    # exclusion funnel
    # the reconciled funnel (s43_corpus_funnel.py); stats.json's collect tallies
    # accumulated `kept` across resumed runs and therefore do not add up
    F = json.load(open(os.path.join(ROOT, "corpus_funnel.json")))
    p = S["corpus"]["pair_screen"]
    stages = [("specific records scanned", F["scanned_specific"]),
              ("with a retrievable document",
               F["scanned_specific"] - F["no_retrievable_document"]),
              ("unique documents retrieved", F["unique_documents"]),
              ("pair-integrity screen OK", p.get("ok", 0) + p.get("partial", 0)),
              ("evaluated: core + extended", e["n_items"] + 18)]
    ax = axes[0]
    ypos = list(range(len(stages)))[::-1]
    ax.barh(ypos, [s[1] for s in stages], color="#7fa8d0", height=0.62)
    for yi, (lab, v) in zip(ypos, stages):
        ax.text(v + 12, yi, f"{v}", va="center", ha="left", fontsize=8, color="#123")
    ax.set_yticks(ypos)
    ax.set_yticklabels([s[0] for s in stages], fontsize=7.8)
    ax.set_xlim(0, max(s[1] for s in stages) * 1.16)
    ax.set_xlabel("documents")
    ax.set_title("(a) Corpus construction", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    # per-item agreement histogram
    ax = axes[1]
    ev = json.load(open(os.path.join(ROOT, "eval_wext_ext.json")))
    per = ev.get("per_item", [])
    accs = [it["match"] / it["pop"] * 100 for it in per if it.get("pop")]
    ax.hist(accs, bins=[80, 84, 88, 92, 96, 98, 100.001],
            color="#2b5c8a", edgecolor="white")
    n_perfect = sum(1 for a in accs if a >= 99.999)
    ax.set_xlabel("registry agreement per document (%)")
    ax.set_ylabel("documents")
    ax.set_title("(b) Per-document registry agreement", fontsize=9)
    ax.annotate(f"{n_perfect} docs at 100%", xy=(100, n_perfect),
                xytext=(90, n_perfect * 0.82), fontsize=7.6, color="#123",
                ha="center", arrowprops=dict(arrowstyle="->", color="#888", lw=0.8))
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGD, "fig4_extended.png"), dpi=400, bbox_inches="tight")
    plt.close()

print("figures written to", os.path.abspath(FIGD))
