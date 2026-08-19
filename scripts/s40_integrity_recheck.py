# -*- coding: utf-8 -*-
"""Verify the methods auditor's two critical claims about Subsection 5.7:

 (a) the 22.9% record-level mismatch is dominated by a few multi-product PDFs, so the
     document-level rate is far lower;
 (b) the sample screen (pair_status.json) and the full-stock screen
     (fullstock_scan.jsonl) disagree on the same UUIDs.
"""
import json, os
from collections import Counter, defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
rows = [json.loads(l) for l in open(os.path.join(ROOT, "fullstock_scan.jsonl"), encoding="utf8")]
spec = [r for r in rows if r.get("status") != "generic"]
checked = [r for r in spec if r.get("status") in ("pair_ok", "pair_partial", "pair_mismatch")]

print("=== (a) record level vs document level ===")
print(f"records checked      : {len(checked)}")
c = Counter(r["status"] for r in checked)
print(f"  record-level        : ok {c['pair_ok']}, partial {c['pair_partial']}, "
      f"mismatch {c['pair_mismatch']}  -> mismatch "
      f"{c['pair_mismatch']/len(checked)*100:.1f}%")

# group by unique document
bydoc = defaultdict(list)
for r in checked:
    bydoc[r.get("pdf_md5")].append(r)
print(f"unique documents      : {len(bydoc)}")

doc_status = {}
for md5, rs in bydoc.items():
    st = Counter(x["status"] for x in rs)
    if st["pair_mismatch"] == len(rs):
        doc_status[md5] = "all_mismatch"
    elif st["pair_mismatch"]:
        doc_status[md5] = "mixed"
    elif st["pair_partial"]:
        doc_status[md5] = "partial"
    else:
        doc_status[md5] = "ok"
dc = Counter(doc_status.values())
print("  document-level      :", dict(dc))
n_bad_docs = dc["all_mismatch"] + dc["mixed"]
print(f"  documents with any mismatch: {n_bad_docs}/{len(bydoc)} = "
      f"{n_bad_docs/len(bydoc)*100:.1f}%")

print("\n  largest multi-product documents by record count:")
big = sorted(bydoc.items(), key=lambda kv: -len(kv[1]))[:6]
tot_mm = c["pair_mismatch"]
cum = 0
for md5, rs in big:
    st = Counter(x["status"] for x in rs)
    cum += st["pair_mismatch"]
    print(f"    {str(md5)[:10]} records={len(rs):4} mismatch={st['pair_mismatch']:4} "
          f"partial={st['pair_partial']:3} ok={st['pair_ok']:3}  e.g. {rs[0]['name'][:38]}")
print(f"  top-6 documents account for {cum}/{tot_mm} = {cum/max(tot_mm,1)*100:.1f}% "
      f"of all record-level mismatches")

print("\n=== (b) sample screen vs full-stock screen on the same UUIDs ===")
pair = json.load(open(os.path.join(ROOT, "pair_status.json")))
full = {r["uuid"]: r.get("status") for r in rows}
MAP = {"ok": "pair_ok", "partial": "pair_partial", "suspect": "pair_mismatch"}
agree = disagree = missing = 0
examples = []
flip = Counter()
for u, s in pair.items():
    s0 = s.split("(")[0]
    f = full.get(u)
    if f is None:
        missing += 1; continue
    want = MAP.get(s0)
    if want == f:
        agree += 1
    else:
        disagree += 1
        flip[f"{s0} -> {f}"] += 1
        if len(examples) < 6:
            examples.append((u[:8], s0, f))
print(f"  common UUIDs: {agree + disagree} (agree {agree}, disagree {disagree}, "
      f"absent from stock scan {missing})")
print("  transitions:", dict(flip))
for e in examples:
    print("   ", e)

out = {"records_checked": len(checked),
       "record_mismatch_pct": round(c["pair_mismatch"] / len(checked) * 100, 1),
       "unique_documents": len(bydoc),
       "doc_status": dict(dc),
       "doc_any_mismatch_pct": round(n_bad_docs / len(bydoc) * 100, 1),
       "top6_share_of_mismatches_pct": round(cum / max(tot_mm, 1) * 100, 1),
       "sample_vs_stock": {"agree": agree, "disagree": disagree,
                           "transitions": dict(flip)}}
json.dump(out, open(os.path.join(ROOT, "integrity_recheck.json"), "w"), indent=1)
print("\nwritten data/integrity_recheck.json")
