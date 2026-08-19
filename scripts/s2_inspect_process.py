"""Step 2: inspect one specific-dataset process: indicator structure + attached docs."""
import requests, json

BASE = "https://oekobaudat.de/OEKOBAU.DAT/resource"
DS = "ca70a7e6-0ea4-4e90-a947-d44585783626"
UUID = "c54c16f6-4295-4749-bff0-ba7ed4bc9117"  # LinCrete GFRC

s = requests.Session()
s.headers.update({"Accept": "application/json", "User-Agent": "UPC-research-pilot/0.1"})

r = s.get(f"{BASE}/datastocks/{DS}/processes/{UUID}", params={"format": "json", "view": "extended"})
r.raise_for_status()
d = r.json()

print("== top-level keys:", list(d.keys()))
pi = d.get("processInformation", {})
print("== name:", json.dumps(pi.get("dataSetInformation", {}).get("name", {}), ensure_ascii=False)[:200])

# LCIA results
lcia = d.get("LCIAResults", {}).get("LCIAResult", [])
print("== n LCIA results:", len(lcia))
if lcia:
    x = lcia[0]
    ref = x.get("referenceToLCIAMethodDataSet", {})
    print("first LCIA method:", json.dumps(ref.get("shortDescription", ""), ensure_ascii=False)[:150])
    other = x.get("other", {}).get("anies", [])
    print("first LCIA 'other' entries:", json.dumps(other[:6], ensure_ascii=False)[:600])

# exchanges (LCI indicators like PERT, also modules)
exch = d.get("exchanges", {}).get("exchange", [])
print("== n exchanges:", len(exch))

# modules declared
mv = d.get("modellingAndValidation", {})
print("== modellingAndValidation keys:", list(mv.keys()))

# sources / attached documents
refs = []
def walk(o, path=""):
    if isinstance(o, dict):
        if o.get("type") == "source data set" or "sources" in str(o.get("resourceURLs", "")):
            refs.append((path, o.get("refObjectId"), json.dumps(o.get("shortDescription", ""), ensure_ascii=False)[:80]))
        for k, v in o.items():
            walk(v, path + "/" + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, path)
walk(d)
print("== source refs found:", len(refs))
for p, u, desc in refs[:15]:
    print(u, desc, "|", p[:80])
