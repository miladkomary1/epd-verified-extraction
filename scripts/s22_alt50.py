import json, os, re
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")
# find ALT 50 uuid
for u in os.listdir(CORPUS):
    gp = os.path.join(CORPUS, u, "gt.json")
    if not os.path.exists(gp): continue
    gt = json.load(open(gp, encoding="utf8"))
    if gt["name"].strip().startswith("ALT 50"):
        d = os.path.join(CORPUS, u); name = gt["name"]; break
text = open(os.path.join(d, "pdftext.txt"), encoding="utf8").read()
print("doc:", name)
print("registry GWP-total modules:", {k: round(v,5) for k,v in gt["indicators"]["GWP-total"]["modules"].items()})
# find GWP-total row in PDF
m = re.search(r"GWP[- ]?total.{0,300}", text)
if m: print("PDF GWP-total row:", repr(m.group(0)[:260]))
m2 = re.search(r"Global Warming Potential total.{0,320}", text)
if m2: print("PDF long GWP row:", repr(m2.group(0)[:280]))
# find module header near it
i = text.find("GWP")
print("context header:", repr(text[max(0,i-260):i][:260]))
