# -*- coding: utf-8 -*-
"""Head-to-head: (a) probe the free Gemini key for usability, (b) run the paper's
exact workflow prompt on the 18 core documents with DeepSeek, saved as llm_ds1.json
so s14_score.py can score it identically."""
import json, os, sys, time, requests

DS = os.environ["DEEPSEEK_KEY"]
GM = os.environ.get("GEMINI_KEY", "")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")
RUN = sys.argv[1] if len(sys.argv) > 1 else "ds1"

# ---- identical to s13_extract_w.py ----
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

# ---------- (a) Gemini free-tier probe ----------
if GM:
    print("=== Gemini free-key probe (6 attempts) ===")
    ok = 0
    for i in range(6):
        try:
            r = requests.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
                params={"key": GM},
                json={"contents": [{"parts": [{"text": "Return ONLY JSON {\"ok\":1}"}]}],
                      "generationConfig": {"responseMimeType": "application/json",
                                           "maxOutputTokens": 50,
                                           "thinkingConfig": {"thinkingBudget": 0}}},
                timeout=60)
            print(f"  attempt {i+1}: {r.status_code}", r.text[:90].replace("\n", " "))
            if r.ok:
                ok += 1
        except Exception as e:
            print(f"  attempt {i+1}: EXC {repr(e)[:80]}")
        time.sleep(5)
    print(f"  -> {ok}/6 succeeded\n")

# ---------- (b) DeepSeek on the 18 core documents ----------
core18 = sorted(u for u in os.listdir(CORPUS)
                if os.path.exists(os.path.join(CORPUS, u, "llm_run1.json")))
usage = {"input_tokens": 0, "output_tokens": 0, "cached": 0, "calls": 0}
print(f"=== DeepSeek workflow run on {len(core18)} core documents ===")
t_start = time.time()
for i, uuid in enumerate(core18):
    d = os.path.join(CORPUS, uuid)
    outp = os.path.join(d, f"llm_{RUN}.json")
    if os.path.exists(outp):
        continue
    gt = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))
    text = focused(open(os.path.join(d, "pdftext.txt"), encoding="utf8").read())
    body = {"model": "deepseek-chat",
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
                time.sleep(6 * (attempt + 1)); continue
            r.raise_for_status()
            dj = r.json()
            u = dj.get("usage", {})
            usage["input_tokens"] += u.get("prompt_tokens", 0)
            usage["output_tokens"] += u.get("completion_tokens", 0)
            usage["cached"] += u.get("prompt_cache_hit_tokens", 0)
            usage["calls"] += 1
            raw = dj["choices"][0]["message"]["content"]
            break
        except Exception as e:
            print("   err:", repr(e)[:90]); time.sleep(5)
    if raw is None:
        print(f"[{i+1}] {gt['name'][:38]} NO OUTPUT"); continue
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"_raw": raw}
    json.dump(parsed, open(outp, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    n = len(parsed.get("indicators", {}) or {})
    print(f"[{i+1}/{len(core18)}] {gt['name'][:38]:40} indicators={n}", flush=True)

el = time.time() - t_start
# DeepSeek list price (USD/1M): cache-miss input 0.27, cache-hit 0.07, output 1.10
cost = usage["input_tokens"] * 0.27e-6 + usage["output_tokens"] * 1.10e-6
usage["cost_usd_est"] = cost
usage["elapsed_s"] = round(el, 1)
json.dump(usage, open(os.path.join(ROOT, f"usage_{RUN}.json"), "w"), indent=1)
print(f"\nusage: {usage}")
print(f"est. cost ${cost:.4f} for {usage['calls']} calls, {el:.0f}s total")
