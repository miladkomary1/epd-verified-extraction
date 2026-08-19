"""Step 9b: arithmetic-gate verdicts.
(1) On the six-row extraction (llm_energy6.json): identities should hold -> pass.
(2) On run2's faulty PERT/PENRT for ArmaFlex, combined with the extracted PERE/PERM
    components: identities must break -> the run2 row-mapping error is flagged.
"""
import json, os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
d = os.path.join(ROOT, "corpus", "3106ccac-01cc-467f-8bff-8a515c575928")
e6 = {k: {m: float(v) for m, v in mods.items()}
      for k, mods in json.load(open(os.path.join(d, "llm_energy6.json"))).items()}
run2 = json.load(open(os.path.join(d, "llm_run2.json"), encoding="utf8"))["indicators"]

def ident(total_vals, a_vals, b_vals, label):
    flags = []
    for m, t in total_vals.items():
        x, y = a_vals.get(m), b_vals.get(m)
        if x is None or y is None:
            continue
        s = x + y
        ok = abs(t - s) <= max(0.025 * max(abs(t), abs(s)), 1e-9)
        if not ok:
            flags.append(f"{m}: total={t:g} vs sum={s:g}")
    print(f"{label}: {'PASS (consistent)' if not flags else 'FLAGGED -> ' + '; '.join(flags)}")

print("=== (1) six-row extraction, identities on the LLM's own values ===")
ident(e6["PERT"], e6["PERE"], e6["PERM"], "PERT = PERE+PERM ")
ident(e6["PENRT"], e6["PENRE"], e6["PENRM"], "PENRT = PENRE+PENRM")

print("\n=== (2) run2 faulty totals + components: gate must flag ===")
r2_pert = {m: float(v) for m, v in run2["PERT"]["values"].items()}
r2_penrt = {m: float(v) for m, v in run2["PENRT"]["values"].items()}
ident(r2_pert, e6["PERE"], e6["PERM"], "run2 PERT vs PERE+PERM ")
ident(r2_penrt, e6["PENRE"], e6["PENRM"], "run2 PENRT vs PENRE+PENRM")
