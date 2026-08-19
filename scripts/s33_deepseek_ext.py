# -*- coding: utf-8 -*-
"""DeepSeek V4-Flash on the 113 extended documents (second-vendor cross-check).
Identical prompt/config to the Gemini wext run; outputs llm_dsext.json per doc."""
import json, os, sys, time, requests

DS = os.environ["DEEPSEEK_KEY"]
MODEL = "deepseek-v4-flash"
RUN = "dsext"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")

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
    return head + "\n[...]\n" + text[idx:idx + 32000] if idx >= 0 else text[:60000]

ext = sorted(u for u in os.listdir(CORPUS)
             if os.path.exists(os.path.join(CORPUS, u, "llm_wext.json")))
usage = {"model": MODEL, "input_tokens": 0, "output_tokens": 0, "calls": 0}
print(f"{MODEL} on {len(ext)} extended documents", flush=True)
t0 = time.time()
for i, uuid in enumerate(ext):
    d = os.path.join(CORPUS, uuid)
    outp = os.path.join(d, f"llm_{RUN}.json")
    if os.path.exists(outp):
        continue
    gt = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))
    text = focused(open(os.path.join(d, "pdftext.txt"), encoding="utf8").read())
    body = {"model": MODEL,
            "messages": [{"role": "user", "content":
                          PROMPT.format(name=gt["name"], codes=", ".join(INDICATORS), text=text)}],
            "response_format": {"type": "json_object"},
            "temperature": 0, "max_tokens": 8000}
    raw = None
    for attempt in range(4):
        try:
            r = requests.post("https://api.deepseek.com/chat/completions",
                              headers={"Authorization": f"Bearer {DS}"}, json=body, timeout=600)
            if r.status_code in (429, 500, 502, 503):
                time.sleep(8 * (attempt + 1)); continue
            r.raise_for_status()
            dj = r.json()
            u = dj.get("usage", {})
            usage["input_tokens"] += u.get("prompt_tokens", 0)
            usage["output_tokens"] += u.get("completion_tokens", 0)
            usage["calls"] += 1
            raw = dj["choices"][0]["message"]["content"]
            break
        except Exception as e:
            print("  err:", repr(e)[:90], flush=True); time.sleep(6)
    if raw is None:
        print(f"[{i+1}] {gt['name'][:36]} NO OUTPUT", flush=True); continue
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"_raw": raw}
    json.dump(parsed, open(outp, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    if (i + 1) % 10 == 0:
        print(f"[{i+1}/{len(ext)}] {(time.time()-t0)/60:.1f} min", flush=True)

cost = usage["input_tokens"] * 0.14e-6 + usage["output_tokens"] * 0.28e-6
usage["cost_usd_est"] = round(cost, 4)
json.dump(usage, open(os.path.join(ROOT, f"usage_{RUN}.json"), "w"), indent=1)
print(f"DONE {usage['calls']} calls, est ${cost:.3f}, {(time.time()-t0)/60:.1f} min", flush=True)
