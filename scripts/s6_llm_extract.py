"""Step 6: LLM extraction of EN 15804 indicator tables from EPD PDF text (Gemini 2.5 Flash).

- schema-less JSON decoding (responseMimeType=application/json, no schema) per PCAP-paper finding
- tracks token usage and estimated cost; hard-stops if projected total exceeds BUDGET_USD
- usage: py s6_llm_extract.py <run_id>   (key read from GEMINI_API_KEY env var)
"""
import json, os, sys, time, re
import requests

RUN = sys.argv[1] if len(sys.argv) > 1 else "run1"
KEY = os.environ["GEMINI_API_KEY"]
MODEL = "gemini-2.5-flash"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
BUDGET_USD = 2.0
PRICE_IN, PRICE_OUT = 0.30 / 1e6, 2.50 / 1e6  # USD per token (Flash, incl. thinking as output)

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")
QUARANTINE = {"215ccde9-9317-4c9c-88b7-afd71e5d2102",   # ALT 100 (EPD pdf missing on server)
              "f518d04d-4805-4d97-b457-9920226f3ff4"}   # LCO White Clinker (no product EPD pdf)

INDICATORS = ["GWP-total", "GWP-fossil", "GWP-biogenic", "GWP-luluc", "ODP", "AP",
              "EP-freshwater", "EP-marine", "EP-terrestrial", "POCP", "ADPE", "ADPF", "WDP",
              "PERT", "PENRT", "FW", "SM", "HWD", "NHWD", "RWD"]

PROMPT = """You are extracting data from the text of an Environmental Product Declaration (EPD) prepared under EN 15804 (+A2).
Target product of this extraction: "{name}"

Extract from the EPD text below:
1. "declared_unit": the declared/functional unit exactly as stated (e.g. "1 m2", "1 kg", "1 t").
2. "indicators": for EACH of these indicator codes that appears in the results tables:
{codes}
   report the numeric value printed for EVERY life-cycle module column present
   (e.g. A1-A3 or A1,A2,A3, A4, A5, B1...B7, C1, C2, C3, C4, D).

Rules:
- Copy the values exactly as printed (scientific notation like 8.47E+02 is fine; output plain JSON numbers).
- If several module columns are aggregated (e.g. "A1-A3"), use that aggregated key.
- If the document covers several products or thicknesses, use only the tables that apply to the target product named above.
- If an indicator or module is not present, omit it. Do not estimate or compute anything.
- Return ONLY JSON, shaped as:
{{"declared_unit": "...", "indicators": {{"GWP-total": {{"unit": "kg CO2 eq", "values": {{"A1-A3": 8.47e2, "A4": 4.35, ...}}}}, ...}}}}

EPD TEXT:
{text}
"""

usage_path = os.path.join(ROOT, f"usage_{RUN}.json")
usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0}

def call_gemini(prompt):
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json",
                             "maxOutputTokens": 16384,
                             "thinkingConfig": {"thinkingBudget": 0}},
    }
    for attempt in range(5):
        r = requests.post(URL, params={"key": KEY}, json=body, timeout=300)
        if r.status_code in (429, 500, 502, 503):
            time.sleep(5 * (attempt + 1)); continue
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

items = [u for u in sorted(os.listdir(CORPUS))
         if os.path.exists(os.path.join(CORPUS, u, "gt.json")) and u not in QUARANTINE]
print(f"{RUN}: extracting {len(items)} items with {MODEL}")

for i, uuid in enumerate(items):
    d = os.path.join(CORPUS, uuid)
    outp = os.path.join(d, f"llm_{RUN}.json")
    if os.path.exists(outp):
        continue
    gt = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))
    text = open(os.path.join(d, "pdftext.txt"), encoding="utf8").read()[:100000]
    prompt = PROMPT.format(name=gt["name"], codes="   " + ", ".join(INDICATORS), text=text)
    raw = call_gemini(prompt)
    if raw is None:
        print(f"[{i+1}] {gt['name'][:40]} -> NO OUTPUT"); continue
    try:
        parsed = json.loads(raw)
        status = "ok"
    except json.JSONDecodeError:
        parsed = {"_raw": raw}
        status = "unparseable"
    json.dump(parsed, open(outp, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    n = len(parsed.get("indicators", {})) if status == "ok" else 0
    print(f"[{i+1}/{len(items)}] {gt['name'][:40]:42} {status} indicators={n} cost so far=${usage['cost_usd']:.3f}")
    json.dump(usage, open(usage_path, "w"), indent=1)
    if usage["cost_usd"] > BUDGET_USD:
        print("BUDGET STOP"); break
    time.sleep(1)

json.dump(usage, open(usage_path, "w"), indent=1)
print("usage:", usage)
