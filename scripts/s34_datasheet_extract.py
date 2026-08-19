# -*- coding: utf-8 -*-
"""ÖKOBAUDAT-compatible record: extract the metadata block + the indicators our
26-code schema omitted (5 output flows + 7 additional impact indicators) for all
131 evaluated documents. Gemini 2.5 Flash via the 3-key free-tier pool."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gemini_client import GeminiPool

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")
RUN = "meta1"

EXTRA = ["GWP-GHG", "PM", "IRP", "ETP-fw", "HTP-c", "HTP-nc", "SQP",
         "CRU", "MFR", "MER", "EEE", "EET"]
MARKERS = ["RESULTS OF THE LCA", "ERGEBNISSE DER ÖKOBILANZ", "LCA: Results",
           "LCA:  Results", "Ergebnisse der Ökobilanz"]

PROMPT = """You are extracting data from the text of an Environmental Product Declaration (EPD) under EN 15804.
Target product: "{name}"

Return ONLY JSON with these fields (use null when not stated in the document):
{{
 "registration_number": "the EPD registration/declaration number, e.g. EPD-XXX-20200142-IBA1-EN",
 "program_operator": "the programme operator/publisher, e.g. Institut Bauen und Umwelt e.V. (IBU)",
 "standard": "the EN 15804 version the EPD complies with, e.g. EN 15804+A2",
 "issue_date": "date of issue as printed (ISO if possible)",
 "valid_until": "validity end date as printed (ISO if possible)",
 "geography": "the geographic scope/production region as printed, e.g. DE, RER, Europe",
 "declared_unit": "the declared/functional unit exactly as stated",
 "indicators": {{
   CODE: {{"unit": "...", "values": {{"A1-A3": ..., "A4": ..., ...}}}}
   for EACH of these codes that appears in the results tables: {codes}
 }}
}}

Rules:
- The additional impact indicators (PM, IRP, ETP-fw, HTP-c, HTP-nc, SQP, GWP-GHG) are
  usually in a separate table titled "additional ... indicators".
- The output flows (CRU components for re-use, MFR materials for recycling, MER materials
  for energy recovery, EEE exported electrical energy, EET exported thermal energy) are in
  the output-flows table; rows may use the long names.
- Copy values exactly as printed; never estimate or compute.
- If the document covers several products, use only tables for the target product.

EPD TEXT:
{text}
"""

def focused(text):
    head = text[:5000]
    low = text.lower()
    idx = min((low.find(m.lower()) for m in MARKERS if low.find(m.lower()) >= 0), default=-1)
    return head + "\n[...]\n" + text[idx:idx + 34000] if idx >= 0 else text[:60000]

if __name__ == "__main__":
    docs = sorted(u for u in os.listdir(CORPUS)
                  if os.path.exists(os.path.join(CORPUS, u, "llm_run1.json"))
                  or os.path.exists(os.path.join(CORPUS, u, "llm_wext.json")))
    print(f"datasheet extraction for {len(docs)} documents", flush=True)

    pool = GeminiPool()
    t0 = time.time()
    n_done = n_fail = 0
    for i, uuid in enumerate(docs):
        d = os.path.join(CORPUS, uuid)
        outp = os.path.join(d, f"llm_{RUN}.json")
        if os.path.exists(outp):
            n_done += 1
            continue
        gt = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))
        text = focused(open(os.path.join(d, "pdftext.txt"), encoding="utf8").read())
        raw, _ = pool.generate(PROMPT.format(name=gt["name"], codes=", ".join(EXTRA), text=text))
        if raw is None:
            n_fail += 1
            print(f"[{i+1}] {gt['name'][:36]} FAILED", flush=True)
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"_raw": raw}
        json.dump(parsed, open(outp, "w", encoding="utf8"), ensure_ascii=False, indent=1)
        n_done += 1
        if (i + 1) % 10 == 0:
            print(f"[{i+1}/{len(docs)}] {(time.time()-t0)/60:.1f} min, "
                  f"usage={pool.usage['calls']} calls, {pool.usage['retries']} retries", flush=True)

    json.dump(pool.cost_report(), open(os.path.join(ROOT, f"usage_{RUN}.json"), "w"), indent=1)
    print(f"\nDONE: {n_done} ok, {n_fail} failed, {(time.time()-t0)/60:.1f} min", flush=True)
    print(json.dumps(pool.cost_report(), indent=1), flush=True)
