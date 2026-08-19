"""Step 19: diagnose extended-corpus disagreements.
Are gated errors concentrated in a few documents (pair mismatch / registry-side) or
spread out (extraction-side)? Cross with pair_status. Also test whether a looser
tolerance (5%) collapses many 'errors' (rounding of 2-sig-fig values)."""
import json, os, math
from collections import defaultdict, Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")
pair = json.load(open(os.path.join(ROOT, "pair_status.json")))
ev = json.load(open(os.path.join(ROOT, "eval_wext_ext.json")))

# per-item error counts from per_item (match/pop) -> errors = pop-match
per = ev["per_item"]
err_by_item = [(it["name"], it.get("pop",0)-it.get("match",0), it.get("pop",0), it["uuid"]) for it in per]
err_by_item.sort(key=lambda x: -x[1])

print(f"total items={len(per)}  total errors(raw)={sum(e[1] for e in err_by_item)}")
docs_with_err = [e for e in err_by_item if e[1] > 0]
print(f"docs with >=1 raw error: {len(docs_with_err)} of {len(per)}")
top = docs_with_err[:12]
print("\ntop error-concentrating docs (raw):")
cum = 0
for name, ne, pop, uuid in top:
    cum += ne
    ps = pair.get(uuid, "?")
    print(f"  {ne:4} err /{pop:4} pop  [{ps:10}]  {name[:44]}")
tot_err = sum(e[1] for e in err_by_item)
print(f"\ntop 12 docs hold {cum}/{tot_err} = {cum/tot_err*100:.0f}% of all raw errors")

# correlate with pair status
by_status = defaultdict(lambda: [0,0,0])  # status -> [docs, errors, pop]
for name, ne, pop, uuid in err_by_item:
    s = pair.get(uuid,"?").split("(")[0]
    by_status[s][0]+=1; by_status[s][1]+=ne; by_status[s][2]+=pop
print("\nerror rate by pair-integrity status:")
for s,(nd,ne,pop) in sorted(by_status.items()):
    print(f"  {s:10} docs={nd:3} errors={ne:4} pop={pop:5} err_rate={ne/pop*100 if pop else 0:.2f}%")
