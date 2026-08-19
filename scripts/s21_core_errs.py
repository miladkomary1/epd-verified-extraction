import json, os, glob
from collections import Counter
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
allerr = []
for f in glob.glob(os.path.join(ROOT, "eval_w*_core.json")):
    ev = json.load(open(f))
    for e in ev["errors"]:
        allerr.append((e["code"], e["mod"], round(e["llm"], 6), round(e["gt"], 6), e["item"][:24]))
c = Counter((e[0], e[1]) for e in allerr)
print("errors across all 10 core W runs (by indicator,module):")
for (code, mod), n in c.most_common():
    ex = next(e for e in allerr if e[0] == code and e[1] == mod)
    print(f"  {code:12} {mod:6} x{n:2}  e.g. llm={ex[2]:.6g} gt={ex[3]:.6g}  [{ex[4]}]")
