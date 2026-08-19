"""Step 10: scale corpus to ~220 paired PDF<->registry EPDs with exclusion accounting.

Improvements over s4: EPD-document source ranking from s4b built in; exclusion
categories recorded (no_pdf_source, fetch_fail, no_text_layer, dup_pdf); resumable.
"""
import requests, json, os, time, io, hashlib
from pypdf import PdfReader

BASE = "https://oekobaudat.de/OEKOBAU.DAT/resource"
DS = "ca70a7e6-0ea4-4e90-a947-d44585783626"  # OBD_2024_I
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")
TARGET = 220
TOTAL = 3216

s = requests.Session()
s.headers.update({"Accept": "application/json", "User-Agent": "UPC-research-pilot/0.1"})

stats_path = os.path.join(ROOT, "collect_stats.json")
stats = {"scanned_specific": 0, "kept": 0, "no_pdf_source": 0, "fetch_fail": 0,
         "no_text_layer": 0, "dup_pdf": 0, "proc_fetch_fail": 0}
seen_md5 = set()
for u in os.listdir(CORPUS):
    p = os.path.join(CORPUS, u, "epd.pdf")
    if os.path.exists(p):
        seen_md5.add(hashlib.md5(open(p, "rb").read()).hexdigest())
        stats["kept"] += 1

def rank(desc, path):
    d = desc.lower(); score = 0
    if "epd document" in d: score += 100
    if "dokument" in d: score += 50
    if "dataSourcesTreatmentAndRepresentativeness/other" in path: score += 40
    if "epd" in d: score += 10
    if any(w in d for w in ("background", "gabi", "database", "datenformat", "format")):
        score -= 80
    return -score

def pdf_sources_ranked(pj):
    hits = []
    def walk(o, path=""):
        if isinstance(o, dict):
            if o.get("type") == "source data set" and o.get("refObjectId"):
                sd = json.dumps(o.get("shortDescription", ""), ensure_ascii=False)
                if ".pdf" in sd.lower():
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
    return sorted(out, key=lambda h: rank(h[1], h[2]))

def fetch_pdf(src_uuid):
    try:
        r = s.get(f"{BASE}/sources/{src_uuid}", params={"format": "json"}, timeout=60)
        if not r.ok: return None
        files = r.json().get("sourceInformation", {}).get("dataSetInformation", {}).get("referenceToDigitalFile", [])
        for f in files:
            uri = f.get("uri", "")
            if uri.lower().endswith(".pdf"):
                fname = uri.split("/")[-1]
                r2 = s.get(f"{BASE}/sources/{src_uuid}/{fname}", timeout=120)
                if r2.ok and r2.headers.get("content-type", "").startswith("application/pdf"):
                    return r2.content
    except requests.RequestException:
        return None
    return None

start = 0
while stats["kept"] < TARGET and start < TOTAL:
    try:
        r = s.get(f"{BASE}/datastocks/{DS}/processes",
                  params={"format": "json", "pageSize": 200, "startIndex": start}, timeout=60)
        r.raise_for_status()
        procs = r.json().get("data", [])
    except requests.RequestException:
        time.sleep(10); continue
    if not procs:
        break
    for p in procs:
        if stats["kept"] >= TARGET:
            break
        if p.get("subType") != "specific dataset":
            continue
        uuid = p["uuid"]
        outdir = os.path.join(CORPUS, uuid)
        if os.path.exists(os.path.join(outdir, "epd.pdf")):
            continue
        stats["scanned_specific"] += 1
        try:
            r = s.get(f"{BASE}/datastocks/{DS}/processes/{uuid}",
                      params={"format": "json", "view": "extended"}, timeout=60)
            if not r.ok:
                stats["proc_fetch_fail"] += 1; continue
            pj = r.json()
        except requests.RequestException:
            stats["proc_fetch_fail"] += 1; continue
        srcs = pdf_sources_ranked(pj)
        if not srcs:
            stats["no_pdf_source"] += 1; continue
        content = None
        for su, _, _ in srcs[:2]:
            content = fetch_pdf(su)
            if content: break
        if not content:
            stats["fetch_fail"] += 1; continue
        md5 = hashlib.md5(content).hexdigest()
        if md5 in seen_md5:
            stats["dup_pdf"] += 1; continue
        try:
            reader = PdfReader(io.BytesIO(content))
            text = "\n\n".join(pg.extract_text() or "" for pg in reader.pages)
        except Exception:
            text = ""
        if len(text) < 2000:
            stats["no_text_layer"] += 1; continue
        os.makedirs(outdir, exist_ok=True)
        json.dump(pj, open(os.path.join(outdir, "registry.json"), "w", encoding="utf8"), ensure_ascii=False)
        open(os.path.join(outdir, "epd.pdf"), "wb").write(content)
        open(os.path.join(outdir, "pdftext.txt"), "w", encoding="utf8").write(text)
        seen_md5.add(md5)
        stats["kept"] += 1
        if stats["kept"] % 10 == 0:
            print(f"kept={stats['kept']} scanned={stats['scanned_specific']} start={start}", flush=True)
            json.dump(stats, open(stats_path, "w"), indent=1)
        time.sleep(0.3)
    start += 200

json.dump(stats, open(stats_path, "w"), indent=1)
print("FINAL", stats)
