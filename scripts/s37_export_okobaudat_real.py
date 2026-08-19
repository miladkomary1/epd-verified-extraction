# -*- coding: utf-8 -*-
"""Export the corpus in the layout OEKOBAUDAT actually publishes.

Replaces s36_export_okobaudat_csv.py, which wrote a layout of our own design
(comma separated, one wide row per product, 651 invented English column names)
and could NOT be appended to a real OEKOBAUDAT export despite the paper saying
so. The schema below was read off a genuine 13,603-row export downloaded from

    https://www.oekobaudat.de/OEKOBAU.DAT/resource/datastocks/{stock}/exportCSV

and its conventions, all verified against that file, are:

  * 100 columns, semicolon separated, the last column empty (trailing ;)
  * ISO-8859-1 (Latin-1), no byte-order mark
  * LONG shape: one row per product and life-cycle module, module in "Modul"
  * document-level columns repeat unchanged on every row of a product
  * plain decimal numbers, never scientific notation, point as separator
  * EN 15804+A2 declarations fill the "(A2)" impact columns and leave the
    unsuffixed ones empty; +A1 declarations do the opposite. In the published
    file no row fills both, so this script does not either.
  * a product not in the registry needs an identifier, so a fresh UUIDv4 is
    generated; "Version" takes 00.01.000, the commonest value among published
    datasets that have no predecessor; "URL" is left empty because every URL in
    the real file resolves to a registry record and this product has none.

The rule the paper is built on carries over: a value is written only if it
passed the verification checks. Withheld or absent leaves an empty cell, and a
module with nothing verified produces no row at all.

usage: py s37_export_okobaudat_real.py [run] [meta_run]
"""
import json, os, sys, uuid, math

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")
OUT = os.path.join(ROOT, "okobaudat_real_export.csv")

# The core indicators live in w1 for the core corpus and in wext for the rest;
# together they cover the 131 documents the paper reports.
RUNS = (sys.argv[1].split(",") if len(sys.argv) > 1 else ["w1", "wext"])
META_RUN = sys.argv[2] if len(sys.argv) > 2 else "meta_ds"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s14_score import norm_mod, load_llm, renderings, CODES, IDENTITIES, arithmetic_flags

COLUMNS = [
    "UUID", "Version", "Name (de)", "Name (en)", "Kategorie (original)", "Kategorie (en)",
    "Konformitaet", "Hintergrunddatenbank(en)", "Laenderkennung", "Typ", "Referenzjahr",
    "Gueltig bis", "URL", "Declaration owner", "Veroeffentlicht am", "Registrierungsnummer",
    "Registrierungsstelle", "UUID des Vorgaengers", "Version des Vorgaengers", "URL des Vorgaengers",
    "Bezugsgroesse", "Bezugseinheit", "Referenzfluss-UUID", "Referenzfluss-Name",
    "Schuettdichte (kg/m3)", "Flaechengewicht (kg/m2)", "Rohdichte (kg/m3)", "Schichtdicke (m)",
    "Ergiebigkeit (m2)", "Laengengewicht (kg/m)", "Stueckgewicht (kg)", "Umrechungsfaktor auf 1kg",
    "biogener Kohlenstoffgehalt in kg", "biogener Kohlenstoffgehalt (Verpackung) in kg",
    "Modul", "Szenario", "Szenariobeschreibung",
    "GWP", "ODP", "POCP", "AP", "EP", "ADPE", "ADPF",
    "PERE", "PERM", "PERT", "PENRE", "PENRM", "PENRT",
    "SM", "RSF", "NRSF", "FW", "HWD", "NHWD", "RWD",
    "CRU", "MFR", "MER", "EEE", "EET",
    "AP (A2)", "GWPtotal (A2)", "GWPbiogenic (A2)", "GWPfossil (A2)", "GWPluluc (A2)",
    "ETPfw (A2)", "PM (A2)", "EPmarine (A2)", "EPfreshwater (A2)", "EPterrestrial (A2)",
    "HTPc (A2)", "HTPnc (A2)", "IRP (A2)", "SOP (A2)", "ODP (A2)", "POCP (A2)",
    "ADPF (A2)", "ADPE (A2)", "WDP (A2)",
    "RMI_FOSSILE", "RMI_METALS", "RMI_MINERALS", "RMI_FORESTRY", "RMI_AGRICULTURE",
    "RMI_FISHERIES", "RMI_ABIOTIC_SUBTOTAL", "RMI_BIOTIC_SUBTOTAL", "RMI_TOTAL",
    "TMR_FOSSILE", "TMR_METALS", "TMR_MINERALS", "TMR_FORESTRY", "TMR_AGRICULTURE",
    "TMR_FISHERIES", "TMR_ABIOTIC_SUBTOTAL", "TMR_BIOTIC_SUBTOTAL", "TMR_TOTAL",
    "",
]

MODULE_ORDER = ["A1", "A2", "A3", "A1-A3", "A4", "A5",
                "B1", "B2", "B3", "B4", "B5", "B6", "B7",
                "C1", "C2", "C3", "C4", "D"]

SHARED = {c: c for c in ["PERE", "PERM", "PERT", "PENRE", "PENRM", "PENRT",
                         "SM", "RSF", "NRSF", "FW", "HWD", "NHWD", "RWD",
                         "CRU", "MFR", "MER", "EEE", "EET"]}

IMPACT_A2 = {
    "GWP-total": "GWPtotal (A2)", "GWP-fossil": "GWPfossil (A2)",
    "GWP-biogenic": "GWPbiogenic (A2)", "GWP-luluc": "GWPluluc (A2)",
    "ODP": "ODP (A2)", "AP": "AP (A2)", "POCP": "POCP (A2)",
    "EP-freshwater": "EPfreshwater (A2)", "EP-marine": "EPmarine (A2)",
    "EP-terrestrial": "EPterrestrial (A2)",
    "ADPE": "ADPE (A2)", "ADPF": "ADPF (A2)", "WDP": "WDP (A2)",
    "PM": "PM (A2)", "IRP": "IRP (A2)", "ETP-fw": "ETPfw (A2)",
    "HTP-c": "HTPc (A2)", "HTP-nc": "HTPnc (A2)",
    "SQP": "SOP (A2)",   # the standard says SQP, OEKOBAUDAT names the column SOP
}
IMPACT_A1 = {"GWP-total": "GWP", "ODP": "ODP", "POCP": "POCP", "AP": "AP",
             "ADPE": "ADPE", "ADPF": "ADPF"}

UNIT_CODES = {
    "m2": "qm", "m²": "qm", "qm": "qm", "sqm": "qm",
    "m3": "m3", "m³": "m3", "cbm": "m3",
    "kg": "kg", "t": "t", "tonne": "t",
    "m": "m", "lfm": "m",
    "piece": "pcs.", "pieces": "pcs.", "pcs": "pcs.", "stk": "pcs.", "stück": "pcs.",
    "mj": "MJ", "a": "a", "kgkm": "kgkm",
}

GEOGRAPHY = {
    "germany": "DE", "deutschland": "DE", "austria": "AT", "switzerland": "CH",
    "france": "FR", "spain": "ES", "italy": "IT", "netherlands": "NL",
    "belgium": "BE", "poland": "PL", "portugal": "PT", "denmark": "DK",
    "sweden": "SE", "norway": "NO", "finland": "FI", "czech republic": "CZ",
    "united kingdom": "GB", "ireland": "IE", "united states": "US", "usa": "US",
    "european union": "EU", "europe": "RER", "global": "GLO", "world": "GLO",
}


def plain_decimal(v):
    """Plain decimal text, never scientific notation, matching the real file."""
    if v is None or v == "":
        return ""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(n):
        return ""
    if n == int(n) and abs(n) < 1e16:
        return str(int(n))
    s = repr(n)
    if "e" not in s and "E" not in s:
        return s
    # expand the exponent by hand rather than losing digits to a fixed format
    mant, exp = s.lower().split("e")
    exp = int(exp)
    neg = mant.startswith("-")
    mant = mant.lstrip("-")
    ip, _, fp = mant.partition(".")
    digits = ip + fp
    point = len(ip) + exp
    if point <= 0:
        out = "0." + "0" * (-point) + digits
    elif point >= len(digits):
        out = digits + "0" * (point - len(digits))
    else:
        out = digits[:point] + "." + digits[point:]
    out = out.rstrip("0").rstrip(".") if "." in out else out
    return ("-" if neg else "") + out


def year_of(value):
    s = str(value or "")
    for i in range(len(s) - 3):
        chunk = s[i:i + 4]
        if chunk.isdigit():
            return chunk
    return ""


def parse_declared_unit(declared):
    """'1 m2 of board' -> ('1', 'qm'). Unrecognised units pass through."""
    s = str(declared or "").strip()
    if not s:
        return "", ""
    tok = ""
    num = ""
    i = 0
    while i < len(s) and (s[i].isdigit() or s[i] in ".,"):
        num += s[i]
        i += 1
    while i < len(s) and s[i] == " ":
        i += 1
    while i < len(s) and not s[i].isspace() and s[i] not in ",;()":
        tok += s[i]
        i += 1
    if not num:
        return "", ""
    tok = tok.rstrip(".,;:")
    return num.replace(",", "."), UNIT_CODES.get(tok.lower(), tok)


def normalize_geography(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    if len(raw) == 2 and raw.isupper():
        return raw
    if raw.upper() in ("RER", "GLO", "EU", "ROW", "RNA"):
        return raw.upper()
    return GEOGRAPHY.get(raw.lower(), raw)


def csv_field(v):
    s = "" if v is None else str(v)
    if any(ch in s for ch in ';"\r\n'):
        return '"' + s.replace('"', '""') + '"'
    return s


def grounded(value, text):
    """The paper's source-grounding gate."""
    return any(r in text for r in renderings(float(value)))


rows_out = []
n_docs = 0
n_written = 0
n_withheld = 0
skipped = []

for u in sorted(os.listdir(CORPUS)):
    d = os.path.join(CORPUS, u)
    core_path = next((os.path.join(d, "llm_%s.json" % r) for r in RUNS
                      if os.path.exists(os.path.join(d, "llm_%s.json" % r))), None)
    meta_path = os.path.join(d, "llm_%s.json" % META_RUN)
    if not (core_path and os.path.exists(meta_path)):
        continue
    gt = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))
    meta = json.load(open(meta_path, encoding="utf8"))
    text = open(os.path.join(d, "pdftext.txt"), encoding="utf8").read()
    for ch in ("\xad", "−", "–"):
        text = text.replace(ch, "-")
    text = text.replace("\xa0", " ")

    core = load_llm(core_path)
    aflags = arithmetic_flags(core)

    # extra indicators live in the metadata run; they carry no identity, so
    # source grounding is the only check available to them
    extra = {}
    for code, obj in (meta.get("indicators") or {}).items():
        if code in CODES or not isinstance(obj, dict):
            continue
        raw = obj.get("values", obj)
        if not isinstance(raw, dict):
            continue
        for m, v in raw.items():
            if isinstance(v, (int, float)):
                extra.setdefault(code, {})[norm_mod(m)] = float(v)

    standard = str(meta.get("standard") or gt.get("standard") or "")
    a2 = "+A2" in standard.replace(" ", "") or any(
        c in core for c in ("GWP-fossil", "GWP-biogenic", "EP-marine"))
    impact = IMPACT_A2 if a2 else IMPACT_A1

    by_module = {}
    for code, mods in list(core.items()) + list(extra.items()):
        column = SHARED.get(code) or impact.get(code)
        if not column:
            continue
        for m, v in mods.items():
            is_core = code in CODES
            ok = grounded(v, text) and not (is_core and (code, m) in aflags)
            if not ok:
                n_withheld += 1
                continue
            by_module.setdefault(m, {})[column] = plain_decimal(v)
            n_written += 1

    if not by_module:
        skipped.append(u)
        continue

    qty, unit = parse_declared_unit(meta.get("declared_unit") or gt.get("declared_unit"))
    conf = standard.strip()
    meta_cells = {
        "UUID": str(uuid.uuid4()),
        "Version": "00.01.000",
        "Name (en)": gt.get("name", ""),
        "Konformitaet": ("'%s'" % conf) if conf else "",
        "Laenderkennung": normalize_geography(meta.get("geography")),
        "Typ": "specific dataset",
        "Referenzjahr": year_of(meta.get("issue_date")),
        "Gueltig bis": year_of(meta.get("valid_until")),
        "Veroeffentlicht am": meta.get("issue_date") or "",
        "Registrierungsnummer": meta.get("registration_number") or "",
        "Registrierungsstelle": meta.get("program_operator") or "",
        "Bezugsgroesse": qty,
        "Bezugseinheit": unit,
        "Referenzfluss-Name": meta.get("declared_unit") or "",
    }

    for m in sorted(by_module, key=lambda x: MODULE_ORDER.index(x) if x in MODULE_ORDER else 99):
        vals = by_module[m]
        row = []
        for c in COLUMNS:
            if c == "Modul":
                row.append(m)
            elif c in meta_cells:
                row.append(meta_cells[c])
            elif c in vals:
                row.append(vals[c])
            else:
                row.append("")
        rows_out.append(row)
    n_docs += 1

with open(OUT, "w", encoding="iso-8859-1", newline="", errors="replace") as f:
    f.write(";".join(csv_field(c) for c in COLUMNS) + "\r\n")
    for r in rows_out:
        f.write(";".join(csv_field(c) for c in r) + "\r\n")

print("wrote %s" % OUT)
print("products: %d, rows: %d, columns: %d" % (n_docs, len(rows_out), len(COLUMNS)))
print("values written: %d, withheld by the checks: %d" % (n_written, n_withheld))
if skipped:
    print("products with nothing verified (no rows): %d" % len(skipped))
