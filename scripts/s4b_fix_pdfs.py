"""Step 4b: re-select the correct EPD PDF per item, preferring 'EPD document' sources."""
import requests, json, os, io, hashlib, time
from pypdf import PdfReader

BASE = "https://oekobaudat.de/OEKOBAU.DAT/resource"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")

s = requests.Session()
s.headers.update({"Accept": "application/json", "User-Agent": "UPC-research-pilot/0.1"})

def all_pdf_sources(pj):
    hits = []
    def walk(o, path=""):
        if isinstance(o, dict):
            if o.get("type") == "source data set" and o.get("refObjectId"):
                sd = json.dumps(o.get("shortDescription", ""), ensure_ascii=False)
                if ".pdf" in sd.lower() or "epd" in sd.lower():
                    hits.append((o["refObjectId"], sd, path))
            for k, v in o.items():
                walk(v, path + "/" + k)
        elif isinstance(o, list):
            for v in o:
                walk(v, path)
    walk(pj)
    seen, out = set(), []
    for h in hits:
        if h[0] not in seen:
            seen.add(h[0]); out.append(h)
    return out

def rank(desc, path):
    d = desc.lower()
    score = 0
    if "epd document" in d: score += 100
    if "dokument" in d: score += 50
    if "dataSourcesTreatmentAndRepresentativeness/other" in path: score += 40  # referenceToOriginalEPD ext
    if d.strip().startswith('"epd'): score += 20
    if "epd" in d: score += 10
    if "fibre cement" in d or "background" in d or "gabi" in d or "database" in d: score -= 50
    return -score

def fetch_pdf(src):
    r = s.get(f"{BASE}/sources/{src}", params={"format": "json"}, timeout=60)
    if not r.ok: return None, None
    files = r.json().get("sourceInformation", {}).get("dataSetInformation", {}).get("referenceToDigitalFile", [])
    for f in files:
        uri = f.get("uri", "")
        if uri.lower().endswith(".pdf"):
            fname = uri.split("/")[-1]
            r2 = s.get(f"{BASE}/sources/{src}/{fname}", timeout=120)
            if r2.ok and r2.headers.get("content-type", "").startswith("application/pdf"):
                return fname, r2.content
    return None, None

for uuid in sorted(os.listdir(CORPUS)):
    d = os.path.join(CORPUS, uuid)
    rj = os.path.join(d, "registry.json")
    if not os.path.exists(rj): continue
    pj = json.load(open(rj, encoding="utf8"))
    name = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))["name"] if os.path.exists(os.path.join(d, "gt.json")) else uuid
    srcs = sorted(all_pdf_sources(pj), key=lambda h: rank(h[1], h[2]))
    if not srcs:
        print("NO SOURCE", name); continue
    best = srcs[0]
    old_md5 = hashlib.md5(open(os.path.join(d, "epd.pdf"), "rb").read()).hexdigest()[:8]
    fname, content = fetch_pdf(best[0])
    if not content:
        print("FETCH FAIL", name, best[1][:60]); continue
    new_md5 = hashlib.md5(content).hexdigest()[:8]
    if new_md5 != old_md5:
        reader = PdfReader(io.BytesIO(content))
        text = "\n\n".join(p.extract_text() or "" for p in reader.pages)
        if len(text) < 2000:
            print("REPLACEMENT HAS NO TEXT LAYER, keeping old:", name); continue
        open(os.path.join(d, "epd.pdf"), "wb").write(content)
        open(os.path.join(d, "pdftext.txt"), "w", encoding="utf8").write(text)
        print(f"REPLACED {name[:40]:42} {old_md5} -> {new_md5}  src={best[1][:60]}")
    else:
        print(f"ok       {name[:40]:42} {old_md5}  src={best[1][:60]}")
    time.sleep(0.3)
