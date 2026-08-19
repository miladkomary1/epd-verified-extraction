"""Step 13: 'workflow' configuration extraction (config W).

Differences vs pilot config (s6):
 - focused input: document head (4k chars) + LCA-results section (30k chars)
 - 26 indicators incl. energy components (PERE/PERM/PENRE/PENRM) -> enables arithmetic gate
 - hint that rows may use long names instead of acronyms

usage: py s13_extract_w.py <run_id> <scope>     scope: core | ext | all
"""
import json, os, sys, time, re, requests

RUN = sys.argv[1]
SCOPE = sys.argv[2] if len(sys.argv) > 2 else "core"
KEY = os.environ["GEMINI_API_KEY"]
MODEL = "gemini-2.5-flash"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
BUDGET_USD = float(os.environ.get("BUDGET_USD", "3.0"))
PRICE_IN, PRICE_OUT = 0.30 / 1e6, 2.50 / 1e6

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")
QUAR = {"215ccde9-9317-4c9c-88b7-afd71e5d2102", "f518d04d-4805-4d97-b457-9920226f3ff4"}

INDICATORS = ["GWP-total", "GWP-fossil", "GWP-biogenic", "GWP-luluc", "ODP", "AP",
              "EP-freshwater", "EP-marine", "EP-terrestrial", "POCP", "ADPE", "ADPF", "WDP",
              "PERE", "PERM", "PERT", "PENRE", "PENRM", "PENRT",
              "SM", "RSF", "NRSF", "FW", "HWD", "NHWD", "RWD"]

MARKERS = ["RESULTS OF THE LCA", "ERGEBNISSE DER ÖKOBILANZ", "LCA: Results",
           "LCA:  Results", "Ergebnisse der Ökobilanz", "RESULTS OF THE LCA -"]

PROMPT = """You are extracting data from the text of an Environmental Product Declaration (EPD) prepared under EN 15804 (+A2).
Target product of this extraction: "{name}"

Extract:
1. "declared_unit": the declared/functional unit exactly as stated.
2. "indicators": for EACH of these EN 15804 indicator codes that appears in the results tables:
   {codes}
   report the numeric value printed for EVERY life-cycle module column present.

Rules:
- The tables may label rows with LONG NAMES instead of acronyms, e.g. "Renewable primary energy as energy carrier" = PERE, "Renewable primary energy resources as material utilization" = PERM, "Total use of renewable primary energy resources" = PERT (same pattern for PENRE/PENRM/PENRT), "Use of secondary material" = SM, "Use of net fresh water" = FW.
- Copy values exactly as printed (scientific notation fine; output plain JSON numbers).
- If the document covers several products, use only tables applying to the target product.
- Omit missing indicators/modules. Never estimate or compute values yourself.
- Return ONLY JSON: {{"declared_unit": "...", "indicators": {{"GWP-total": {{"unit": "...", "values": {{"A1-A3": ..., ...}}}}, ...}}}}

EPD TEXT:
{text}
"""

def focused(text):
    head = text[:4000]
    low = text.lower()
    idx = min((low.find(m.lower()) for m in MARKERS if low.find(m.lower()) >= 0), default=-1)
    if idx >= 0:
        return head + "\n[...]\n" + text[idx:idx + 32000]
    return text[:60000]

usage_path = os.path.join(ROOT, f"usage_{RUN}.json")
usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0}

def call(prompt):
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json",
                                 "maxOutputTokens": 16384,
                                 "thinkingConfig": {"thinkingBudget": 0}}}
    for attempt in range(6):
        try:
            r = requests.post(URL, params={"key": KEY}, json=body, timeout=300)
        except requests.RequestException:
            time.sleep(8); continue
        if r.status_code in (429, 500, 502, 503):
            time.sleep(6 * (attempt + 1)); continue
        r.raise_for_status()
        d = r.json()
        um = d.get("usageMetadata", {})
        usage["input_tokens"] += um.get("promptTokenCount", 0)
        usage["output_tokens"] += um.get("candidatesTokenCount", 0) + um.get("thoughtsTokenCount", 0)
        usage["calls"] += 1
        usage["cost_usd"] = usage["input_tokens"] * PRICE_IN + usage["output_tokens"] * PRICE_OUT
        try:
            return d["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            return None
    return None

core18 = sorted(u for u in os.listdir(CORPUS)
                if os.path.exists(os.path.join(CORPUS, u, "llm_run1.json")))
ps_path = os.path.join(ROOT, "pair_status.json")
suspects = set()
if os.path.exists(ps_path):
    suspects = {u for u, v in json.load(open(ps_path)).items() if v == "suspect"}
all_items = sorted(u for u in os.listdir(CORPUS)
                   if os.path.exists(os.path.join(CORPUS, u, "gt.json"))
                   and u not in QUAR and u not in suspects)
items = {"core": core18, "ext": [u for u in all_items if u not in core18], "all": all_items}[SCOPE]
lim = int(os.environ.get("EXT_LIMIT", "0"))
if lim and SCOPE == "ext":
    items = items[:lim]
print(f"{RUN} scope={SCOPE}: {len(items)} items")

for i, uuid in enumerate(items):
    d = os.path.join(CORPUS, uuid)
    outp = os.path.join(d, f"llm_{RUN}.json")
    if os.path.exists(outp):
        continue
    gt = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))
    text = focused(open(os.path.join(d, "pdftext.txt"), encoding="utf8").read())
    raw = call(PROMPT.format(name=gt["name"], codes=", ".join(INDICATORS), text=text))
    if raw is None:
        print(f"[{i+1}] {gt['name'][:40]} NO OUTPUT", flush=True); continue
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"_raw": raw}
    json.dump(parsed, open(outp, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    if (i + 1) % 10 == 0 or i == len(items) - 1:
        print(f"[{i+1}/{len(items)}] cost=${usage['cost_usd']:.3f}", flush=True)
    json.dump(usage, open(usage_path, "w"), indent=1)
    if usage["cost_usd"] > BUDGET_USD:
        print("BUDGET STOP", flush=True); break
    time.sleep(0.8)

json.dump(usage, open(usage_path, "w"), indent=1)
print("usage:", usage)
