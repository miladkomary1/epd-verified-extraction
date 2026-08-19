"""Step 1: explore OKOBAUDAT soda4LCA API - find EPD processes with attached PDFs."""
import requests, json, sys

BASE = "https://oekobaudat.de/OEKOBAU.DAT/resource"
DS = "ca70a7e6-0ea4-4e90-a947-d44585783626"  # OBD_2024_I

s = requests.Session()
s.headers.update({"Accept": "application/json", "User-Agent": "UPC-research-pilot/0.1"})

# list processes
r = s.get(f"{BASE}/datastocks/{DS}/processes", params={"format": "json", "pageSize": 200, "startIndex": 0})
r.raise_for_status()
d = r.json()
print("totalCount:", d.get("totalCount"))
procs = d.get("data", [])
print("page size:", len(procs))
# show structure of first entries
for p in procs[:5]:
    print(json.dumps({k: p.get(k) for k in ("uuid", "name", "subType", "classific", "dsType")}, ensure_ascii=False)[:300])
