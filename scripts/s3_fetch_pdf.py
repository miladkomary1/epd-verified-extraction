"""Step 3: resolve a source dataset to its digital PDF file and download it."""
import requests, json, os

BASE = "https://oekobaudat.de/OEKOBAU.DAT/resource"
SRC = "d1d9893d-2d5b-44fe-a55c-151303189a64"  # 'LinCrete' EPD pdf source
OUT = os.path.join(os.path.dirname(__file__), "data", "sample")
os.makedirs(OUT, exist_ok=True)

s = requests.Session()
s.headers.update({"Accept": "application/json", "User-Agent": "UPC-research-pilot/0.1"})

r = s.get(f"{BASE}/sources/{SRC}", params={"format": "json"})
print("source meta status:", r.status_code)
if r.ok:
    d = r.json()
    print(json.dumps(d, ensure_ascii=False)[:1500])

# soda4LCA digital file listing
r2 = s.get(f"{BASE}/sources/{SRC}/digitalfiles", params={"format": "json"})
print("\ndigitalfiles status:", r2.status_code, r2.headers.get("content-type"))
print(r2.text[:800])
