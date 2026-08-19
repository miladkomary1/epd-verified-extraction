# -*- coding: utf-8 -*-
"""Full-stock registry scan: every process record in OBD_2024_I.

For each record: subType; for manufacturer-specific ones additionally:
PDF source presence, retrievability, text layer, and the anchor-value pair
integrity screen (GWP-total, GWP-fossil, PERT, PENRT at A1-A3/A1).

PDFs are processed in memory and discarded (no 3 GB corpus); text extraction is
cached per source uuid because multi-product declarations share one PDF.
Resumable: already-scanned uuids in the JSONL are skipped.
"""
import json, os, re, io, time, math, hashlib
import requests
from pypdf import PdfReader

BASE = "https://oekobaudat.de/OEKOBAU.DAT/resource"
DS = "ca70a7e6-0ea4-4e90-a947-d44585783626"  # OBD_2024_I
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUT = os.path.join(ROOT, "fullstock_scan.jsonl")

s = requests.Session()
s.headers.update({"Accept": "application/json", "User-Agent": "UPC-research-scan/0.2"})

done = set()
if os.path.exists(OUT):
    for line in open(OUT, encoding="utf8"):
        try:
            done.add(json.loads(line)["uuid"])
        except Exception:
            pass
print(f"resuming: {len(done)} records already scanned", flush=True)

pdf_text_cache = {}   # source_uuid -> (md5, n_chars, text or None)

def en(sd):
    if isinstance(sd, list):
        for x in sd:
            if isinstance(x, dict) and x.get("lang") == "en":
                return x.get("value", "")
        for x in sd:
            if isinstance(x, dict):
                return x.get("value", "")
    return str(sd or "")

def renderings(v):
    outs = set()
    if v == 0:
        return {"0.00E+0", "0.00E+00"}
    neg = "-" if v < 0 else ""
    av = abs(v); exp = math.floor(math.log10(av))
    for sig in (2, 3, 4):
        mant = round(av / 10**exp, sig - 1); e = exp
        if mant >= 10:
            mant /= 10; e += 1
        dec = f"{mant:.{sig-1}f}"
        dec2 = dec.rstrip("0").rstrip(".") if "." in dec else dec
        sign = "+" if e >= 0 else "-"
        for dsx in {dec, dec2, dec.replace(".", ","), dec2.replace(".", ",")}:
            for es in (f"{abs(e)}", f"{abs(e):02d}"):
                outs.add(f"{neg}{dsx}E{sign}{es}")
        r = round(v, max(0, sig - 1 - exp))
        outs.add(f"{r:g}"); outs.add(f"{r:g}".replace(".", ","))
    return outs

def anchors_from_process(pj):
    vals = {}
    for x in pj.get("LCIAResults", {}).get("LCIAResult", []):
        nm = en(x.get("referenceToLCIAMethodDataSet", {}).get("shortDescription"))
        m = re.search(r"\(([A-Za-z\-]+)\)\s*$", nm.strip())
        code = m.group(1) if m else None
        if code not in ("GWP-total", "GWP-fossil"):
            continue
        for a in x.get("other", {}).get("anies", []):
            if isinstance(a, dict) and a.get("module") in ("A1-A3", "A1") and "value" in a:
                try:
                    vals[code] = float(a["value"]); break
                except (TypeError, ValueError):
                    pass
    for x in pj.get("exchanges", {}).get("exchange", []):
        nm = en(x.get("referenceToFlowDataSet", {}).get("shortDescription"))
        m = re.search(r"\(([A-Za-z\-]+)\)\s*$", nm.strip())
        code = m.group(1) if m else None
        if code not in ("PERT", "PENRT"):
            continue
        for a in x.get("other", {}).get("anies", []):
            if isinstance(a, dict) and a.get("module") in ("A1-A3", "A1") and "value" in a:
                try:
                    vals[code] = float(a["value"]); break
                except (TypeError, ValueError):
                    pass
    return vals

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
    def rank(desc, path):
        d = desc.lower(); score = 0
        if "epd document" in d: score += 100
        if "dokument" in d: score += 50
        if "dataSourcesTreatmentAndRepresentativeness/other" in path: score += 40
        if "epd" in d: score += 10
        if any(w in d for w in ("background", "gabi", "database", "datenformat", "format")):
            score -= 80
        return -score
    return sorted(out, key=lambda h: rank(h[1], h[2]))

def fetch_pdf_text(src_uuid):
    if src_uuid in pdf_text_cache:
        return pdf_text_cache[src_uuid]
    result = (None, 0, None)
    try:
        r = s.get(f"{BASE}/sources/{src_uuid}", params={"format": "json"}, timeout=45)
        if r.ok:
            files = (r.json().get("sourceInformation", {}).get("dataSetInformation", {})
                     .get("referenceToDigitalFile", []))
            for f in files:
                uri = f.get("uri", "")
                if not uri.lower().endswith(".pdf"):
                    continue
                fname = uri.split("/")[-1]
                r2 = s.get(f"{BASE}/sources/{src_uuid}/{fname}", timeout=90)
                if r2.ok and r2.headers.get("content-type", "").startswith("application/pdf"):
                    md5 = hashlib.md5(r2.content).hexdigest()
                    try:
                        reader = PdfReader(io.BytesIO(r2.content))
                        text = "\n".join(p.extract_text() or "" for p in reader.pages)
                    except Exception:
                        text = ""
                    for ch in ("\xad", "−", "–"):
                        text = text.replace(ch, "-")
                    text = text.replace("\xa0", " ")
                    result = (md5, len(text), text if len(text) >= 2000 else None)
                    break
    except requests.RequestException:
        pass
    pdf_text_cache[src_uuid] = result
    if len(pdf_text_cache) > 400:   # bound memory
        for k in list(pdf_text_cache)[:100]:
            del pdf_text_cache[k]
    return result

t0 = time.time()
n_new = 0
outf = open(OUT, "a", encoding="utf8")
start = 0
while True:
    try:
        r = s.get(f"{BASE}/datastocks/{DS}/processes",
                  params={"format": "json", "pageSize": 500, "startIndex": start}, timeout=60)
        r.raise_for_status()
        page = r.json()
    except requests.RequestException as e:
        print("page fetch error, retrying:", repr(e)[:80], flush=True)
        time.sleep(15); continue
    procs = page.get("data", [])
    if not procs:
        break
    for p in procs:
        uuid = p.get("uuid")
        if not uuid or uuid in done:
            continue
        row = {"uuid": uuid, "name": p.get("name", "")[:80],
               "subType": p.get("subType", ""), "classific": p.get("classific", "")[:60]}
        if p.get("subType") == "specific dataset":
            try:
                pr = s.get(f"{BASE}/datastocks/{DS}/processes/{uuid}",
                           params={"format": "json", "view": "extended"}, timeout=60)
                if not pr.ok:
                    row["status"] = "proc_fetch_fail"
                else:
                    pj = pr.json()
                    srcs = pdf_sources_ranked(pj)
                    if not srcs:
                        row["status"] = "no_pdf_source"
                    else:
                        md5 = None; nchars = 0; text = None
                        for su, _, _ in srcs[:2]:
                            md5, nchars, text = fetch_pdf_text(su)
                            if md5:
                                row["src_uuid"] = su
                                break
                        if md5 is None:
                            row["status"] = "pdf_fetch_fail"
                        elif text is None:
                            row["status"] = "no_text_layer"
                            row["pdf_md5"] = md5; row["chars"] = nchars
                        else:
                            row["pdf_md5"] = md5; row["chars"] = nchars
                            anchors = anchors_from_process(pj)
                            found = sum(1 for v in anchors.values()
                                        if any(x in text for x in renderings(v)))
                            row["anchors_tested"] = len(anchors)
                            row["anchors_found"] = found
                            if len(anchors) == 0:
                                row["status"] = "no_anchor_values"
                            elif found == 0:
                                row["status"] = "pair_mismatch"
                            elif found < len(anchors):
                                row["status"] = "pair_partial"
                            else:
                                row["status"] = "pair_ok"
            except Exception as e:
                row["status"] = "error:" + repr(e)[:60]
        else:
            row["status"] = "generic"
        outf.write(json.dumps(row, ensure_ascii=False) + "\n")
        outf.flush()
        done.add(uuid)
        n_new += 1
        if n_new % 25 == 0:
            el = time.time() - t0
            print(f"scanned {n_new} new ({len(done)} total) in {el/60:.1f} min "
                  f"({el/max(n_new,1):.1f}s/rec)", flush=True)
        time.sleep(0.25)
    start += 500

outf.close()
print(f"\nDONE: {len(done)} records in {(time.time()-t0)/60:.1f} min", flush=True)

# summary
from collections import Counter
c = Counter(json.loads(l)["status"] for l in open(OUT, encoding="utf8"))
print(json.dumps(dict(c), indent=1))
