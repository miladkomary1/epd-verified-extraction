"""Step 20: confirm the carpet-cluster failure mode = multi-product declaration."""
import json, os, re
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")
ev = json.load(open(os.path.join(ROOT, "eval_wext_ext.json")))

# find a Tufted-tiles doc
target = None
for it in ev["per_item"]:
    if "Tufted tiles" in it["name"] and it.get("pop",0)-it.get("match",0) == 22:
        target = it["uuid"]; name = it["name"]; break
d = os.path.join(CORPUS, target)
text = open(os.path.join(d, "pdftext.txt"), encoding="utf8").read()
gt = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))
print("doc:", name)
print("registry declared_unit:", gt.get("declared_unit"))
# how many product/EPD result-table headers?
n_gwp = len(re.findall(r"GWP-total|Global Warming Potential total|Globales Erw", text))
n_tables = len(re.findall(r"RESULTS OF THE LCA|Ergebnisse der Ökobilanz", text, re.I))
print("occurrences of GWP-total label:", n_gwp, "| results-table markers:", n_tables)
# list distinct product-ish headings
prods = set(re.findall(r"(Tufted[^\n]{0,40}|Woven[^\n]{0,40})", text))
print("product-like strings in PDF (first 8):")
for p in list(prods)[:8]:
    print("   ", p.strip()[:60])
# show GWP-total registry vs one printed value
gwp = gt["indicators"].get("GWP-total",{}).get("modules",{}).get("A1-A3")
print("\nregistry GWP-total A1-A3:", gwp)
# find all A1-A3-ish GWP numbers printed
m = re.search(r"GWP-total.{0,400}", text)
if m: print("first GWP row context:", repr(m.group(0)[:200]))
