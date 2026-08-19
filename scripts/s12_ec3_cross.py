"""Step 12: EC3 cross-registry check on the core documents.

For each core EPD, search EC3 by product name; if a confident name match exists,
compare EC3's EF 3.0 module values against the OKOBAUDAT registry values for
GWP-total, ODP, AP, POCP (A1-A3). Measures registry-to-registry agreement — the
'silver truth' quality bound discussed in the paper.
"""
import json, os, re, time, requests

H = {"Authorization": "Bearer " + os.environ["EC3_KEY"], "Accept": "application/json"}
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")

MAP = {"GWP-total": "gwp", "ODP": "odp", "AP": "ap", "POCP": "pocp"}

def name_key(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())

core18 = sorted(u for u in os.listdir(CORPUS)
                if os.path.exists(os.path.join(CORPUS, u, "llm_run1.json")))
results = []
for uuid in core18:
    d = os.path.join(CORPUS, uuid)
    gt = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))
    name = gt["name"].strip()
    try:
        r = requests.get("https://buildingtransparency.org/api/epds",
                         params={"page_size": 10, "q": name[:60]}, headers=H, timeout=60)
        rows = r.json() if isinstance(r.json(), list) else r.json().get("results", [])
    except Exception:
        rows = []
    match = None
    for e in rows:
        if name_key(e.get("name", ""))[:40] == name_key(name)[:40]:
            match = e; break
    if not match:
        results.append({"uuid": uuid, "name": name[:40], "ec3": None})
        continue
    try:
        det = requests.get(f"https://buildingtransparency.org/api/epds/{match['id']}",
                           headers=H, timeout=60).json()
    except Exception:
        results.append({"uuid": uuid, "name": name[:40], "ec3": None}); continue
    imp = (det.get("impacts") or {}).get("EF 3.0", {})
    comp = {}
    for code, k in MAP.items():
        obd = gt["indicators"].get(code, {}).get("modules", {}).get("A1-A3")
        node = imp.get(k, {})
        ec3 = None
        for mk in ("A1A2A3", "A1-A3"):
            if mk in node:
                ec3 = node[mk].get("mean"); break
        if obd is not None and ec3 is not None and obd != 0:
            comp[code] = {"obd": obd, "ec3": ec3, "rel_diff_pct": abs(ec3 - obd) / abs(obd) * 100}
    results.append({"uuid": uuid, "name": name[:40], "ec3": match["id"], "comparison": comp})
    time.sleep(0.5)

json.dump(results, open(os.path.join(ROOT, "ec3_cross.json"), "w"), indent=1)
matched = [r for r in results if r.get("comparison")]
print(f"core docs: {len(results)}, matched in EC3 with EF3.0 impacts: {len(matched)}")
agree = 0; tot = 0
for r in matched:
    for code, c in r["comparison"].items():
        tot += 1
        ok = c["rel_diff_pct"] <= 2.5
        agree += ok
        if not ok:
            print(f"  DISAGREE {r['name'][:30]} {code}: OBD={c['obd']:.4g} EC3={c['ec3']:.4g} ({c['rel_diff_pct']:.1f}%)")
print(f"registry-to-registry agreement (<=2.5%): {agree}/{tot}")
