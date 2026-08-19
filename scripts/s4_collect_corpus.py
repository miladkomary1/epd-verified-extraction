"""Step 4: collect paired PDF <-> registry EPD corpus from OKOBAUDAT (target 20 pairs).

For each 'specific dataset' process in OBD_2024_I:
  - fetch extended ILCD JSON
  - locate the 'EPD document ... .pdf' source reference (referenceToOriginalEPD extension)
  - download the PDF via /resource/sources/{uuid}/{filename}
  - keep pair if PDF has a text layer (>2000 chars via pypdf)
Saves: data/corpus/{uuid}/registry.json, epd.pdf, pdftext.txt and data/manifest.json
"""
import requests, json, os, time, re, sys, io
from pypdf import PdfReader

BASE = "https://oekobaudat.de/OEKOBAU.DAT/resource"
DS = "ca70a7e6-0ea4-4e90-a947-d44585783626"  # OBD_2024_I
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")
os.makedirs(CORPUS, exist_ok=True)
TARGET = 20

s = requests.Session()
s.headers.update({"Accept": "application/json", "User-Agent": "UPC-research-pilot/0.1"})

def list_processes(start, size=200):
    r = s.get(f"{BASE}/datastocks/{DS}/processes",
              params={"format": "json", "pageSize": size, "startIndex": start}, timeout=60)
    r.raise_for_status()
    return r.json()

def find_epd_pdf_sources(proc_json):
    """Return list of (source_uuid, shortDescription) that look like the original EPD pdf."""
    hits = []
    def walk(o):
        if isinstance(o, dict):
            if o.get("type") == "source data set" and o.get("refObjectId"):
                sd = o.get("shortDescription")
                txt = json.dumps(sd, ensure_ascii=False) if sd is not None else ""
                if ".pdf" in txt.lower():
                    hits.append((o["refObjectId"], txt))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(proc_json)
    # dedupe preserving order
    seen, out = set(), []
    for u, t in hits:
        if u not in seen:
            seen.add(u); out.append((u, t))
    return out

def download_pdf(src_uuid):
    r = s.get(f"{BASE}/sources/{src_uuid}", params={"format": "json"}, timeout=60)
    if not r.ok:
        return None, None
    meta = r.json()
    files = meta.get("sourceInformation", {}).get("dataSetInformation", {}).get("referenceToDigitalFile", [])
    for f in files:
        uri = f.get("uri", "")
        if not uri.lower().endswith(".pdf"):
            continue
        fname = uri.split("/")[-1]
        r2 = s.get(f"{BASE}/sources/{src_uuid}/{fname}", timeout=120)
        if r2.ok and r2.headers.get("content-type", "").startswith("application/pdf"):
            return fname, r2.content
    return None, None

def pdf_text(content):
    try:
        reader = PdfReader(io.BytesIO(content))
        pages = [p.extract_text() or "" for p in reader.pages]
        return "\n\n".join(pages), len(reader.pages)
    except Exception as e:
        return "", 0

manifest = []
kept = 0
start = 0
scanned = 0
while kept < TARGET and start < 3216:
    page = list_processes(start)
    procs = page.get("data", [])
    if not procs:
        break
    for p in procs:
        if kept >= TARGET:
            break
        scanned += 1
        if p.get("subType") != "specific dataset":
            continue
        uuid = p["uuid"]
        outdir = os.path.join(CORPUS, uuid)
        if os.path.exists(os.path.join(outdir, "epd.pdf")):
            kept += 1
            continue
        try:
            r = s.get(f"{BASE}/datastocks/{DS}/processes/{uuid}",
                      params={"format": "json", "view": "extended"}, timeout=60)
            if not r.ok:
                continue
            pj = r.json()
            srcs = find_epd_pdf_sources(pj)
            # prefer sources whose description mentions 'EPD' or ends with product-ish pdf
            if not srcs:
                continue
            fname = content = None
            for su, _ in srcs:
                fname, content = download_pdf(su)
                if content:
                    break
            if not content:
                continue
            text, npages = pdf_text(content)
            if len(text) < 2000:
                manifest.append({"uuid": uuid, "name": p.get("name"), "status": "no_text_layer", "pages": npages})
                continue
            os.makedirs(outdir, exist_ok=True)
            with open(os.path.join(outdir, "registry.json"), "w", encoding="utf8") as f:
                json.dump(pj, f, ensure_ascii=False)
            with open(os.path.join(outdir, "epd.pdf"), "wb") as f:
                f.write(content)
            with open(os.path.join(outdir, "pdftext.txt"), "w", encoding="utf8") as f:
                f.write(text)
            kept += 1
            manifest.append({"uuid": uuid, "name": p.get("name"), "status": "ok",
                             "pdf": fname, "pages": npages, "chars": len(text),
                             "classific": p.get("classific")})
            print(f"[{kept}/{TARGET}] {p.get('name')!r} pages={npages} chars={len(text)}")
            time.sleep(0.4)
        except Exception as e:
            print("ERR", uuid, repr(e)[:120])
    start += 200

with open(os.path.join(ROOT, "manifest.json"), "w", encoding="utf8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=1)
print(f"\nDone. kept={kept} scanned={scanned} manifest entries={len(manifest)}")
