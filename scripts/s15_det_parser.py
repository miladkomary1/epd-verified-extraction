"""Step 15: deterministic table-parser baseline (no LLM, no cost).

Strategy (precision-first):
 1. normalize unicode (soft hyphen/minus/nbsp)
 2. locate results-table header lines: '<label> <Unit> <module tokens...>'
 3. parse rows: code from '(CODE)' parentheses, leading acronym, or long-name dictionary
 4. take trailing numeric tokens; keep row only if count == number of module columns
Writes llm_det.json per document (same shape as LLM output) so s14 can score it.
"""
import json, os, re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")

CODES = {"GWP-total", "GWP-fossil", "GWP-biogenic", "GWP-luluc", "ODP", "AP",
         "EP-freshwater", "EP-marine", "EP-terrestrial", "POCP", "ADPE", "ADPF", "WDP",
         "PERE", "PERM", "PERT", "PENRE", "PENRM", "PENRT",
         "SM", "RSF", "NRSF", "FW", "HWD", "NHWD", "RWD"}
MODULE_TOKEN = re.compile(r"^(A1-A3|A1|A2|A3|A4|A5|B1|B2|B3|B4|B5|B6|B7|C1|C2|C3|C4|D)$")
NUM = re.compile(r"^[+-]?(\d+([.,]\d+)?([Ee][+-]?\d+)?|\d+[.,]?\d*)$")
PAREN_CODE = re.compile(r"\(([A-Za-z]+(?:-[A-Za-z]+)?)\)")

LONG_EN = [
    ("total use of renewable primary energy", "PERT"),
    ("renewable primary energy resources as material", "PERM"),
    ("renewable primary energy as energy carrier", "PERE"),
    ("total use of non renewable primary energy", "PENRT"),
    ("total use of non-renewable primary energy", "PENRT"),
    ("non renewable primary energy as material", "PENRM"),
    ("non-renewable primary energy as material", "PENRM"),
    ("non renewable primary energy as energy carrier", "PENRE"),
    ("non-renewable primary energy as energy carrier", "PENRE"),
    ("use of secondary material", "SM"),
    ("use of renewable secondary fuels", "RSF"),
    ("use of non renewable secondary fuels", "NRSF"),
    ("use of non-renewable secondary fuels", "NRSF"),
    ("use of net fresh water", "FW"),
    ("hazardous waste disposed", "HWD"),
    ("non hazardous waste disposed", "NHWD"),
    ("non-hazardous waste disposed", "NHWD"),
    ("radioactive waste disposed", "RWD"),
    ("global warming potential total", "GWP-total"),
    ("global warming potential fossil", "GWP-fossil"),
    ("global warming potential biogenic", "GWP-biogenic"),
    ("global warming potential luluc", "GWP-luluc"),
    ("depletion potential of the stratospheric ozone", "ODP"),
    ("acidification potential", "AP"),
    ("eutrophication potential of freshwater", "EP-freshwater"),
    ("eutrophication aquatic freshwater", "EP-freshwater"),
    ("eutrophication potential of marine", "EP-marine"),
    ("eutrophication aquatic marine", "EP-marine"),
    ("eutrophication potential of terrestrial", "EP-terrestrial"),
    ("eutrophication terrestrial", "EP-terrestrial"),
    ("formation potential of tropospheric ozone", "POCP"),
    ("photochemical ozone", "POCP"),
    ("abiotic depletion potential for non fossil", "ADPE"),
    ("abiotic depletion potential for non-fossil", "ADPE"),
    ("abiotic depletion for non-fossil", "ADPE"),
    ("abiotic depletion potential for fossil", "ADPF"),
    ("abiotic depletion for fossil resources", "ADPF"),
    ("water (user) deprivation potential", "WDP"),
    ("water use", "WDP"),
]

def parse_num(tok):
    tok = tok.replace(",", ".")
    try:
        return float(tok)
    except ValueError:
        return None

def row_code(label):
    m = PAREN_CODE.search(label)
    if m and m.group(1) in CODES:
        return m.group(1)
    first = label.split()[0] if label.split() else ""
    first = first.strip("():;,")
    if first in CODES:
        return first
    low = label.lower()
    # NHWD before HWD etc: LONG_EN ordered specific-first
    for pat, code in LONG_EN:
        if pat in low:
            return code
    return None

def parse_doc(text):
    for ch in ("\xad", "−", "–"):
        text = text.replace(ch, "-")
    text = text.replace("\xa0", " ")
    lines = text.split("\n")
    out = {}
    modules = None
    for ln in lines:
        toks = ln.split()
        if not toks:
            continue
        # header detection: >=3 module tokens and few other tokens
        mods = [t for t in toks if MODULE_TOKEN.match(t)]
        if len(mods) >= 3 and len(mods) >= len(toks) - 2:
            modules = mods
            continue
        if not modules:
            continue
        # row: trailing numeric tokens
        nums = []
        for t in reversed(toks):
            v = parse_num(t) if NUM.match(t) else None
            if v is None:
                break
            nums.append(v)
        nums.reverse()
        if len(nums) != len(modules) or not nums:
            continue
        label = " ".join(toks[:len(toks) - len(nums)])
        code = row_code(label)
        if code and code not in out:
            out[code] = {"values": dict(zip(modules, nums))}
    return out

n_done = 0
tot_rows = 0
for uuid in sorted(os.listdir(CORPUS)):
    d = os.path.join(CORPUS, uuid)
    tp = os.path.join(d, "pdftext.txt")
    if not os.path.exists(tp):
        continue
    res = parse_doc(open(tp, encoding="utf8").read())
    json.dump({"indicators": res}, open(os.path.join(d, "llm_det.json"), "w"), indent=1)
    n_done += 1
    tot_rows += len(res)
print(f"parsed {n_done} docs, mean indicators/doc = {tot_rows/n_done:.1f}")
