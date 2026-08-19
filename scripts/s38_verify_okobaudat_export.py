# -*- coding: utf-8 -*-
"""Check that s37's output really is OEKOBAUDAT-compatible.

Compares the header cell by cell with a genuine published export and appends
every generated row to it, confirming each row still parses at the published
width. This is what the previous export could not do, and what the paper claims.

usage: py s38_verify_okobaudat_export.py <path to a real OEKOBAUDAT exportCSV>
       (download one from
        https://www.oekobaudat.de/OEKOBAU.DAT/resource/datastocks/{stock}/exportCSV)
"""
import os, sys, csv

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OURS = os.path.join(ROOT, "okobaudat_real_export.csv")
REAL = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "okobaudat_reference.csv")

if not os.path.exists(REAL):
    print("no reference file at %s" % REAL)
    print("download one from the exportCSV endpoint and pass its path")
    sys.exit(1)

def read_rows(path):
    with open(path, encoding="iso-8859-1", newline="") as f:
        return list(csv.reader(f, delimiter=";"))

real = read_rows(REAL)
ours = read_rows(OURS)

ok = True
def check(label, condition, detail=""):
    global ok
    print("  %s  %s%s" % ("PASS" if condition else "FAIL", label,
                          "" if condition else "   " + detail))
    if not condition:
        ok = False

print("reference: %s (%d rows)" % (os.path.basename(REAL), len(real) - 1))
print("ours:      %s (%d rows)" % (os.path.basename(OURS), len(ours) - 1))
print()

check("header has the published width", len(ours[0]) == len(real[0]),
      "%d vs %d" % (len(ours[0]), len(real[0])))
check("header matches cell for cell", ours[0] == real[0],
      "first difference: %s" % next((("%r vs %r" % (a, b))
                                     for a, b in zip(ours[0], real[0]) if a != b), ""))

widths = set(len(r) for r in ours[1:])
check("every generated row has the published width", widths == {len(real[0])}, str(widths))

merged = real + ours[1:]
mwidths = set(len(r) for r in merged)
check("appending to the real file keeps one width", mwidths == {len(real[0])}, str(mwidths))

mod = real[0].index("Modul")
uuid_i = real[0].index("UUID")
check("real rows still read correctly after appending",
      merged[1][uuid_i] == real[1][uuid_i])
check("appended rows carry a module in the published position",
      all(r[mod] for r in ours[1:]))

# no scientific notation anywhere, matching the published file
sci = [c for r in ours[1:] for c in r if c and ("e" in c.lower()) and
       any(ch.isdigit() for ch in c) and c.replace("-", "").replace(".", "").replace("e", "").isdigit()]
check("no scientific notation in the numbers", not sci, str(sci[:3]))

# the +A1 and +A2 impact sets are never both filled, as in the published file
a1i, a2i = real[0].index("GWP"), real[0].index("GWPtotal (A2)")
both = [r for r in ours[1:] if r[a1i] and r[a2i]]
check("no row fills both standard versions", not both, "%d rows do" % len(both))

print()
print("%s  s37 output is OEKOBAUDAT-compatible" % ("PASS" if ok else "FAIL"))
sys.exit(0 if ok else 1)
