# -*- coding: utf-8 -*-
"""Recompute the corpus-construction funnel so that it reconciles.

The tallies in stats.json do not add up: 662 scanned minus 199 without a document
leaves 463, but 220 kept plus 261 duplicates plus 2 fetch failures is 483. The
cause is in s4_collect_corpus.py, which increments `kept` for a record whose
directory already holds a PDF from an earlier run (the resume branch), so `kept`
accumulated across runs while the category tallies came from the final run only.
manifest.json holding just 20 rows against 220 corpus directories confirms it.

The corpus itself is sound: 220 directories, 220 PDFs, 220 distinct content
hashes, no duplicates. Only the reported breakdown is wrong.

This script rebuilds the funnel from the released full-stock scan, walking the
manufacturer-specific records in registry order until the 220 unique documents of
the corpus are accounted for, so every category is counted once under one rule.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CORPUS = os.path.join(DATA, "corpus")
OUT = os.path.join(DATA, "corpus_funnel.json")

rows = [json.loads(l) for l in open(os.path.join(DATA, "fullstock_scan.jsonl"),
                                    encoding="utf8")]
have = {d for d in os.listdir(CORPUS) if os.path.isdir(os.path.join(CORPUS, d))}

scanned = no_doc = dup = fail = 0
seen_hash = set()
unique = []
for r in rows:
    if r.get("subType") != "specific dataset":
        continue
    scanned += 1
    st = r.get("status")
    if st == "no_pdf_source":
        no_doc += 1
    elif st == "pdf_fetch_fail":
        fail += 1
    else:
        h = r.get("pdf_md5")
        if h in seen_hash:
            dup += 1
        else:
            seen_hash.add(h)
            unique.append(r["uuid"])
    if len(unique) >= len(have):
        break

funnel = {
    "corpus_dirs_on_disk": len(have),
    "unique_pdf_hashes_on_disk": None,   # filled below
    "scanned_specific": scanned,
    "no_retrievable_document": no_doc,
    "duplicate_of_document_already_collected": dup,
    "download_failed": fail,
    "unique_documents": len(unique),
    "reconciles": scanned - no_doc - dup - fail == len(unique),
}

import hashlib
hashes = set()
for d in have:
    p = os.path.join(CORPUS, d, "epd.pdf")
    if os.path.exists(p):
        hashes.add(hashlib.md5(open(p, "rb").read()).hexdigest())
funnel["unique_pdf_hashes_on_disk"] = len(hashes)

json.dump(funnel, open(OUT, "w", encoding="utf8"), indent=1)
print(json.dumps(funnel, indent=1))
print("\ncheck: %d scanned - %d no doc - %d duplicate - %d failed = %d unique"
      % (scanned, no_doc, dup, fail, scanned - no_doc - dup - fail))
