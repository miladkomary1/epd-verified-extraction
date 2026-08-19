"""Verify the ChatGPT audit's numerical claims against the actual experiment data."""
import json, os, glob
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")

print("== C2: naive per-run errors (raw and gated) ==")
for r in ("run1", "run2", "run3"):
    ev = json.load(open(os.path.join(ROOT, f"eval_{r}_core.json")))
    print(f"  {r}: raw_errors={ev['n_errors']}  gated_surfaced={ev['gated_errors_surfaced']}")

print("\n== C4: extended docs with zero populated slots ==")
ev = json.load(open(os.path.join(ROOT, "eval_wext_ext.json")))
per = ev["per_item"]
zero = [it for it in per if not it.get("pop")]
perfect = [it for it in per if it.get("pop") and it["match"] == it["pop"]]
imperfect = [it for it in per if it.get("pop") and it["match"] < it["pop"]]
print(f"  total={len(per)}  zero-pop={len(zero)}  perfect={len(perfect)}  imperfect={len(imperfect)}")
for it in zero:
    print("    zero-pop doc:", it["name"][:50], "gt_slots:", it["gt_slots"])

print("\n== C3: partial-pair cohort split ==")
pair = json.load(open(os.path.join(ROOT, "pair_status.json")))
core18 = sorted(u for u in os.listdir(CORPUS)
                if os.path.exists(os.path.join(CORPUS, u, "llm_run1.json")))
ext = [u for u in os.listdir(CORPUS) if os.path.exists(os.path.join(CORPUS, u, "llm_wext.json"))]
cats = {"core": core18, "ext": ext}
for status in ("ok", "partial", "suspect"):
    n_core = sum(1 for u in core18 if pair.get(u, "").startswith(status))
    n_ext = sum(1 for u in ext if pair.get(u, "").startswith(status))
    n_all = sum(1 for u, v in pair.items() if v.startswith(status))
    print(f"  {status}: total={n_all} core={n_core} ext={n_ext} not_evaluated={n_all-n_core-n_ext}")
n_uneval = sum(1 for u, v in pair.items()
               if not v.startswith("suspect") and u not in core18 and u not in ext
               and os.path.exists(os.path.join(CORPUS, u, "gt.json")))
print(f"  retained but not evaluated: {n_uneval}")

print("\n== C6: measured token/cost totals across ALL usage files ==")
tin = tout = calls = cost = 0
for f in glob.glob(os.path.join(ROOT, "usage_*.json")):
    u = json.load(open(f))
    tin += u["input_tokens"]; tout += u["output_tokens"]
    calls += u["calls"]; cost += u["cost_usd"]
print(f"  calls={calls}  input={tin/1e6:.2f}M  output={tout/1e6:.2f}M  cost=${cost:.2f}")
print(f"  check: {tin}*0.30/1e6 + {tout}*2.50/1e6 = ${tin*0.3e-6 + tout*2.5e-6:.2f}")

print("\n== C7: LinCrete mapping check ==")
lin = "c54c16f6-4295-4749-bff0-ba7ed4bc9117"
gt = json.load(open(os.path.join(CORPUS, lin, "gt.json"), encoding="utf8"))
print("  OBD GWP-total A1-A3:", gt["indicators"]["GWP-total"]["modules"]["A1-A3"])
print("  OBD GWP-fossil A1-A3:", gt["indicators"]["GWP-fossil"]["modules"]["A1-A3"])
ec3 = json.load(open(os.path.join(ROOT, "ec3_cross.json")))
for r in ec3:
    if r.get("comparison") and "LinCrete" in r["name"]:
        print("  EC3 comparison:", json.dumps(r["comparison"].get("GWP-total"), indent=2))

print("\n== Wilson CI for 22/24 ==")
import math
p, n = 22/24, 24
z = 1.96
denom = 1 + z*z/n
centre = (p + z*z/(2*n)) / denom
half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / denom
print(f"  91.7%, Wilson 95% CI: {100*(centre-half):.1f}% to {100*(centre+half):.1f}%")

print("\n== naive run raw errors detail (run1) ==")
ev1 = json.load(open(os.path.join(ROOT, "eval_run1_core.json")))
for e in ev1["errors"]:
    print("   run1 error:", e["code"], e["mod"], e["llm"], "vs", e["gt"])
