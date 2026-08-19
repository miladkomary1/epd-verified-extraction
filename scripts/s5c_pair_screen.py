"""Step 5c: pair-integrity screen over the whole corpus.
A pair is SUSPECT (likely wrong/mismatched PDF) if neither GWP-total nor PENRT
(A1-A3 or A1) registry value is locatable in the PDF text. Writes data/pair_status.json.
"""
import json, os, math

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")

def renderings(v):
    outs = set()
    if v == 0:
        return {"0.00E+0", "0.00E+00"}
    neg = "-" if v < 0 else ""
    av = abs(v); exp = math.floor(math.log10(av))
    for sig in (2, 3, 4):
        mant = round(av / 10**exp, sig - 1); e = exp
        if mant >= 10: mant /= 10; e += 1
        dec = f"{mant:.{sig-1}f}"
        dec2 = dec.rstrip("0").rstrip(".") if "." in dec else dec
        sign = "+" if e >= 0 else "-"
        for ds in {dec, dec2, dec.replace(".", ","), dec2.replace(".", ",")}:
            for es in (f"{abs(e)}", f"{abs(e):02d}"):
                outs.add(f"{neg}{ds}E{sign}{es}")
        r = round(v, max(0, sig - 1 - exp))
        outs.add(f"{r:g}"); outs.add(f"{r:g}".replace(".", ","))
    return outs

status = {}
for uuid in sorted(os.listdir(CORPUS)):
    d = os.path.join(CORPUS, uuid)
    gp = os.path.join(d, "gt.json")
    if not os.path.exists(gp):
        status[uuid] = "no_gt"; continue
    gt = json.load(open(gp, encoding="utf8"))
    text = open(os.path.join(d, "pdftext.txt"), encoding="utf8").read()
    for ch in ("\xad", "−", "–"):
        text = text.replace(ch, "-")
    text = text.replace("\xa0", " ")
    found = 0; tested = 0
    for code in ("GWP-total", "PENRT", "GWP-fossil", "PERT"):
        ind = gt["indicators"].get(code)
        if not ind: continue
        v = ind["modules"].get("A1-A3", ind["modules"].get("A1"))
        if v is None: continue
        tested += 1
        if any(r in text for r in renderings(v)):
            found += 1
    if tested == 0:
        status[uuid] = "no_anchor"
    elif found == 0:
        status[uuid] = "suspect"
    elif found < tested:
        status[uuid] = f"partial({found}/{tested})"
    else:
        status[uuid] = "ok"

from collections import Counter
c = Counter(v.split("(")[0] for v in status.values())
print(dict(c))
json.dump(status, open(os.path.join(ROOT, "pair_status.json"), "w"), indent=1)
suspects = [u for u, v in status.items() if v == "suspect"]
print("suspect pairs:", len(suspects))
for u in suspects[:15]:
    gt = json.load(open(os.path.join(CORPUS, u, "gt.json"), encoding="utf8"))
    print("  ", u[:8], gt["name"][:60])
