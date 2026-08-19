"""Step 23: extra data for manuscript v2.
(a) full reference strings reused from PCAP v17 -> refs_pcap.json
(b) per-indicator and per-module accuracy across the 10 core w-runs
(c) worked example rows (LinCrete)
(d) run-range statistics
Writes data/ms_extra.json
"""
import json, os, re, glob, math
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")

# ---------- (a) reusable references from the companion procurement study ----------
# That manuscript is not part of this repository. Point PCAP_TEXT at its exported
# text file to regenerate refs_pcap.json; sections (b) to (d) run without it.
PCAP_TEXT = os.environ.get("PCAP_TEXT", "")
if PCAP_TEXT and os.path.exists(PCAP_TEXT):
    text = open(PCAP_TEXT, encoding="utf8").read()
    i = text.rfind("References")
    ref_lines = [l.strip() for l in text[i:].split("\n")
                 if re.match(r"\[\d+\]", l.strip())]
    refs = {}
    for l in ref_lines:
        m = re.match(r"\[(\d+)\](.*)", l)
        refs[int(m.group(1))] = m.group(2).strip()
    json.dump(refs, open(os.path.join(ROOT, "refs_pcap.json"), "w", encoding="utf8"),
              ensure_ascii=False, indent=1)
else:
    print("(a) skipped: set PCAP_TEXT to the companion study's exported text")
print(f"(a) extracted {len(refs)} PCAP references")

# ---------- (b) per-indicator / per-module over w1..w10 core ----------
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s14_score import CODES, norm_mod, matches, load_llm

core18 = sorted(u for u in os.listdir(CORPUS)
                if os.path.exists(os.path.join(CORPUS, u, "llm_run1.json")))
ind_stat = defaultdict(lambda: [0, 0, 0])   # code -> [gt, pop, match] summed over runs
mod_stat = defaultdict(lambda: [0, 0, 0])
runs = [f"w{i}" for i in range(1, 11)]
for run in runs:
    for uuid in core18:
        d = os.path.join(CORPUS, uuid)
        gt = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))
        llm = load_llm(os.path.join(d, f"llm_{run}.json"))
        for code in CODES:
            g = gt["indicators"].get(code)
            if not g:
                continue
            gmods = {norm_mod(k): v for k, v in g["modules"].items()}
            lvals = llm.get(code, {})
            for m, gv in gmods.items():
                ind_stat[code][0] += 1; mod_stat[m][0] += 1
                if m in lvals:
                    ind_stat[code][1] += 1; mod_stat[m][1] += 1
                    ok = matches(lvals[m], gv)
                    ind_stat[code][2] += ok; mod_stat[m][2] += ok

per_ind = {c: {"gt": v[0], "pop": v[1], "match": v[2],
               "cov_pct": v[1] / v[0] * 100 if v[0] else 0,
               "acc_pct": v[2] / v[1] * 100 if v[1] else 0} for c, v in ind_stat.items()}
per_mod = {m: {"gt": v[0], "pop": v[1], "match": v[2],
               "cov_pct": v[1] / v[0] * 100 if v[0] else 0,
               "acc_pct": v[2] / v[1] * 100 if v[1] else 0} for m, v in mod_stat.items()}

# ---------- (c) worked example: LinCrete ----------
lin = "c54c16f6-4295-4749-bff0-ba7ed4bc9117"
d = os.path.join(CORPUS, lin)
gt = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))
llm = load_llm(os.path.join(d, "llm_w1.json"))
raw = json.load(open(os.path.join(d, "llm_w1.json"), encoding="utf8"))
we_rows = []
for code in ("GWP-total", "GWP-fossil", "PERT", "PENRT", "FW", "NHWD"):
    g = gt["indicators"].get(code, {})
    unit = g.get("unit", "")
    gv = g.get("modules", {}).get("A1-A3")
    lv = llm.get(code, {}).get("A1-A3")
    we_rows.append({"code": code, "unit": unit, "extracted": lv, "registry": gv,
                    "match": (lv is not None and gv is not None and matches(lv, gv))})
worked = {"name": gt["name"], "declared_unit": raw.get("declared_unit", ""), "rows": we_rows}

# ---------- (d) run ranges ----------
evs = [json.load(open(os.path.join(ROOT, f"eval_{r}_core.json"))) for r in runs]
rng = {
    "prec_min": min(e["precision_pct"] for e in evs),
    "prec_max": max(e["precision_pct"] for e in evs),
    "err_min": min(e["n_errors"] for e in evs),
    "err_max": max(e["n_errors"] for e in evs),
    "gated_err_all": [e["gated_errors_surfaced"] for e in evs],
}
nevs = [json.load(open(os.path.join(ROOT, f"eval_{r}_core.json"))) for r in ("run1", "run2", "run3")]
rng_naive = {"err": [e["n_errors"] for e in nevs],
             "gated_surfaced": [e["gated_errors_surfaced"] for e in nevs]}

json.dump({"per_ind": per_ind, "per_mod": per_mod, "worked": worked,
           "ranges": rng, "ranges_naive": rng_naive},
          open(os.path.join(ROOT, "ms_extra.json"), "w", encoding="utf8"),
          ensure_ascii=False, indent=1)
print("(b) per-indicator worst:", sorted(per_ind.items(), key=lambda x: x[1]["acc_pct"])[:3])
print("(c) worked example:", worked["name"], worked["declared_unit"], we_rows[0])
print("(d) ranges:", rng)
