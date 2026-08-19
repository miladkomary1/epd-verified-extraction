"""Step 18: aggregate every number the manuscript needs into data/stats.json."""
import json, os, math, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s14_score import score_run, mean_ci

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")

S = {}

# --- corpus accounting ---
collect = json.load(open(os.path.join(ROOT, "collect_stats.json")))
pair = json.load(open(os.path.join(ROOT, "pair_status.json")))
from collections import Counter
pc = Counter(v.split("(")[0] for v in pair.values())
S["corpus"] = {"collect": collect, "pair_screen": dict(pc),
               "n_docs": len([u for u in os.listdir(CORPUS)
                              if os.path.exists(os.path.join(CORPUS, u, "gt.json"))])}

# --- core runs ---
wruns = [f"w{i}" for i in range(1, 11)
         if any(os.path.exists(os.path.join(CORPUS, u, f"llm_w{i}.json"))
                for u in os.listdir(CORPUS))]
nruns = ["run1", "run2", "run3"]
S["core_w"] = {"runs": []}
for r in wruns:
    S["core_w"]["runs"].append(score_run(r, "core"))
S["core_naive"] = {"runs": [score_run(r, "core") for r in nruns]}
S["det_core"] = score_run("det", "core")

def agg(runs, keys):
    out = {}
    for k in keys:
        m, ci = mean_ci([r[k] for r in runs])
        out[k] = {"mean": m, "ci": ci}
    return out

KEYS = ["coverage_pct", "precision_pct", "recall_pct", "n_errors",
        "gated_coverage_pct", "gated_precision_pct", "gated_errors_surfaced",
        "errors_withheld", "correct_withheld"]
S["core_w"]["agg"] = agg(S["core_w"]["runs"], KEYS)
S["core_naive"]["agg"] = agg(S["core_naive"]["runs"], KEYS)

# --- extended ---
if any(os.path.exists(os.path.join(CORPUS, u, "llm_wext.json")) for u in os.listdir(CORPUS)):
    S["ext_w"] = score_run("wext", "ext")
    S["det_ext"] = score_run("det", "ext")

# --- extended diagnostics ---
if "ext_w" in S:
    pair = json.load(open(os.path.join(ROOT, "pair_status.json")))
    ev = json.load(open(os.path.join(ROOT, "eval_wext_ext.json")))
    per = ev["per_item"]
    errs = sorted(((it.get("pop", 0) - it.get("match", 0), it) for it in per),
                  key=lambda x: -x[0])
    tot_err = sum(e for e, _ in errs)
    docs_with_err = sum(1 for e, _ in errs if e > 0)
    top12 = sum(e for e, _ in errs[:12])
    from collections import defaultdict
    by_status = defaultdict(lambda: [0, 0, 0])
    for e, it in errs:
        st = pair.get(it["uuid"], "?").split("(")[0]
        by_status[st][0] += 1; by_status[st][1] += e; by_status[st][2] += it.get("pop", 0)
    S["ext_diag"] = {
        "total_raw_errors": tot_err, "docs_total": len(per),
        "docs_with_error": docs_with_err, "top12_share_pct": top12 / tot_err * 100 if tot_err else 0,
        "worst_doc_errors": errs[0][0], "worst_doc_pop": errs[0][1].get("pop", 0),
        "worst_doc_name": errs[0][1]["name"],
        "by_status": {k: {"docs": v[0], "errors": v[1], "pop": v[2],
                          "err_rate_pct": v[1] / v[2] * 100 if v[2] else 0}
                      for k, v in by_status.items()},
    }

# --- strict schema ---
p = os.path.join(ROOT, "strict_schema_outcome.json")
if os.path.exists(p):
    S["strict_schema"] = json.load(open(p))
    S["strict_schema"].pop("errors", None)

# --- EC3 cross ---
p = os.path.join(ROOT, "ec3_cross.json")
if os.path.exists(p):
    ec3 = json.load(open(p))
    matched = [r for r in ec3 if r.get("comparison")]
    tot = sum(len(r["comparison"]) for r in matched)
    agree = sum(1 for r in matched for c in r["comparison"].values() if c["rel_diff_pct"] <= 2.5)
    dis = [{"name": r["name"], "code": k, **c} for r in matched
           for k, c in r["comparison"].items() if c["rel_diff_pct"] > 2.5]
    S["ec3"] = {"n_core": len(ec3), "n_matched": len(matched), "n_compared": tot,
                "n_agree": agree, "disagreements": dis}

# --- cost ---
costs = {}
for f in os.listdir(ROOT):
    if f.startswith("usage_"):
        u = json.load(open(os.path.join(ROOT, f)))
        costs[f.replace("usage_", "").replace(".json", "")] = u
S["cost"] = costs
S["cost_per_doc_usd"] = {k: v["cost_usd"] / max(v["calls"], 1) for k, v in costs.items()}
S["total_spend_usd"] = sum(v["cost_usd"] for v in costs.values())

# --- declared unit accuracy on core (w1) ---
du_ok = du_tot = 0
core18 = sorted(u for u in os.listdir(CORPUS)
                if os.path.exists(os.path.join(CORPUS, u, "llm_run1.json")))
for u in core18:
    d = os.path.join(CORPUS, u)
    gt = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))
    lp = os.path.join(d, "llm_w1.json")
    if not os.path.exists(lp): continue
    llm = json.load(open(lp, encoding="utf8"))
    g = (gt.get("declared_unit") or "").lower().replace(" ", "")
    l = (llm.get("declared_unit") or "").lower().replace(" ", "")
    if g:
        du_tot += 1
        du_ok += (g in l or l in g) and bool(l)
S["declared_unit"] = {"ok": du_ok, "total": du_tot}

json.dump(S, open(os.path.join(ROOT, "stats.json"), "w"), indent=1)
print("=== stats.json written ===")
print(f"docs: {S['corpus']['n_docs']}, w-runs: {len(wruns)}")
print("core W agg:", {k: f"{v['mean']:.2f}pm{v['ci']:.2f}" for k, v in S['core_w']['agg'].items()})
if "ext_w" in S:
    e = S["ext_w"]
    print(f"ext: n={e['n_items']} cov={e['coverage_pct']:.1f} prec={e['precision_pct']:.2f} "
          f"gatedprec={e['gated_precision_pct']:.2f} errSurf={e['gated_errors_surfaced']}")
print("total spend USD:", round(S["total_spend_usd"], 3))
