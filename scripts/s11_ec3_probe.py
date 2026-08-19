import requests, json, os
H = {"Authorization": "Bearer " + os.environ["EC3_KEY"], "Accept": "application/json"}
r = requests.get("https://buildingtransparency.org/api/epds",
                 params={"page_size": 5, "q": "AQUAPANEL"}, headers=H, timeout=60)
print(r.status_code)
d = r.json()
rows = d if isinstance(d, list) else d.get("results", [])
for e in rows:
    print(e.get("name", "")[:60], "| pdf:", str(e.get("pdf_url"))[:80], "| id:", e.get("id"))
if rows:
    eid = rows[0]["id"]
    r2 = requests.get(f"https://buildingtransparency.org/api/epds/{eid}", headers=H, timeout=60)
    print("detail:", r2.status_code)
    if r2.ok:
        det = r2.json()
        imp = det.get("impacts") or {}
        print("impacts methods:", list(imp)[:5])
        for meth, vals in list(imp.items())[:1]:
            print("sample:", json.dumps(vals)[:300])
        print("pdf fields:", {k: str(det.get(k))[:70] for k in ("pdf_url", "doc", "original_ecd_url", "manufacturer_specific")} )
