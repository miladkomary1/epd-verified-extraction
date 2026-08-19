"""Step 5b: pair sanity check — does the registry GWP-total (and PENRT) A1-A3 value
appear in the PDF text in any common numeric rendering? Also refresh pdf_md5 in gt.json."""
import json, os, re, math, hashlib

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")

def renderings(v):
    """Common ways a value like 847.351015 appears in EPD tables."""
    outs = set()
    if v == 0:
        return {"0", "0.00E+00", "0,00", "0.0"}
    for sig in (2, 3, 4):
        # scientific notation 8.47E+02 / 8,47E+02 / 8.47E+2
        exp = math.floor(math.log10(abs(v)))
        mant = round(v / 10**exp, sig - 1)
        if abs(mant) >= 10:  # rounding pushed it up
            mant /= 10; exp += 1
        for dec in (f"{mant:.{sig-1}f}",):
            outs.add(f"{dec}E+{exp:02d}" if exp >= 0 else f"{dec}E-{abs(exp):02d}")
            outs.add(f"{dec}E+{exp}" if exp >= 0 else f"{dec}E-{abs(exp)}")
            outs.add(f"{dec.replace('.', ',')}E+{exp:02d}" if exp >= 0 else f"{dec.replace('.', ',')}E-{abs(exp):02d}")
        # plain decimal
        r = round(v, max(0, sig - 1 - exp))
        outs.add(f"{r:g}")
        outs.add(f"{r:g}".replace(".", ","))
    return outs

rows = []
for uuid in sorted(os.listdir(CORPUS)):
    d = os.path.join(CORPUS, uuid)
    gtp = os.path.join(d, "gt.json")
    if not os.path.exists(gtp):
        continue
    gt = json.load(open(gtp, encoding="utf8"))
    gt["pdf_md5"] = hashlib.md5(open(os.path.join(d, "epd.pdf"), "rb").read()).hexdigest()
    json.dump(gt, open(gtp, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    text = open(os.path.join(d, "pdftext.txt"), encoding="utf8").read()
    text_norm = text.replace(" ", " ")
    checks = {}
    for code in ("GWP-total", "PENRT", "AP"):
        ind = gt["indicators"].get(code)
        if not ind:
            checks[code] = "absent"
            continue
        mod = ind["modules"].get("A1-A3") or ind["modules"].get("A1")
        if mod is None:
            checks[code] = "no A1-A3"
            continue
        found = any(r in text_norm for r in renderings(mod))
        checks[code] = "FOUND" if found else f"MISS({mod:.4g})"
    name_token = gt["name"].split()[0].strip("'‘’")[:12]
    name_in = name_token.lower() in text.lower()
    rows.append((gt["name"][:38], name_in, checks))

ok = 0
for name, name_in, checks in rows:
    status = all(v == "FOUND" for v in checks.values())
    ok += status
    print(f"{'PASS' if status else 'WARN'}  {name:40.38} name_in_pdf={name_in}  {checks}")
print(f"\n{ok}/{len(rows)} items: all three anchor values found verbatim in PDF text")
