# -*- coding: utf-8 -*-
"""Verify two round-2 audit claims before writing them into the paper:
 (1) the screen disagreement is caused by different PDFs being fetched, not by a
     different ranking rule;
 (2) the 33% no-document rate varies substantially by product category.
"""
import json, os, hashlib
from collections import Counter, defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")
rows = [json.loads(l) for l in open(os.path.join(ROOT, "fullstock_scan.jsonl"), encoding="utf8")]
byuuid = {r["uuid"]: r for r in rows}
pair = json.load(open(os.path.join(ROOT, "pair_status.json")))

print("=== (1) do the two screens see the same PDF? ===")
MAP = {"ok": "pair_ok", "partial": "pair_partial", "suspect": "pair_mismatch"}
same_pdf = diff_pdf = no_local = 0
disputed_same = disputed_diff = 0
for u, s in pair.items():
    r = byuuid.get(u)
    if not r or not r.get("pdf_md5"):
        continue
    p = os.path.join(CORPUS, u, "epd.pdf")
    if not os.path.exists(p):
        no_local += 1
        continue
    local = hashlib.md5(open(p, "rb").read()).hexdigest()
    agree = MAP.get(s.split("(")[0]) == r["status"]
    if local == r["pdf_md5"]:
        same_pdf += 1
        if not agree:
            disputed_same += 1
    else:
        diff_pdf += 1
        if not agree:
            disputed_diff += 1
print(f"  records comparable      : {same_pdf + diff_pdf} (no local copy: {no_local})")
print(f"  identical PDF (md5)     : {same_pdf}")
print(f"  different PDF (md5)     : {diff_pdf}")
print(f"  screen disagreements on identical PDFs : {disputed_same}")
print(f"  screen disagreements on different PDFs : {disputed_diff}")
if disputed_same:
    print("  -> some disagreement is NOT explained by a different document")

print("\n=== (2) no-document rate by product category ===")
spec = [r for r in rows if r.get("status") != "generic"]
bycat = defaultdict(lambda: [0, 0])
for r in spec:
    cat = (r.get("classific") or "unknown").split("/")[0].strip()[:40] or "unknown"
    bycat[cat][1] += 1
    if r["status"] == "no_pdf_source":
        bycat[cat][0] += 1
rowsout = sorted(((c, n, tot, n / tot * 100) for c, (n, tot) in bycat.items() if tot >= 25),
                 key=lambda x: -x[3])
for c, n, tot, pct in rowsout:
    print(f"  {c[:38]:40} {n:4}/{tot:4} = {pct:5.1f}%")
overall = sum(1 for r in spec if r["status"] == "no_pdf_source") / len(spec) * 100
print(f"  overall: {overall:.1f}%  |  spread across categories with >=25 records: "
      f"{min(x[3] for x in rowsout):.1f}% to {max(x[3] for x in rowsout):.1f}%")

json.dump({"screen_same_pdf": same_pdf, "screen_diff_pdf": diff_pdf,
           "disagree_same_pdf": disputed_same, "disagree_diff_pdf": disputed_diff,
           "cat_min_pct": round(min(x[3] for x in rowsout), 1),
           "cat_max_pct": round(max(x[3] for x in rowsout), 1),
           "cat_table": [(c, n, tot, round(p, 1)) for c, n, tot, p in rowsout]},
          open(os.path.join(ROOT, "round2_checks.json"), "w"), indent=1)
print("\nwritten data/round2_checks.json")
