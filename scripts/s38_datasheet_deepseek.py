# -*- coding: utf-8 -*-
"""Datasheet extraction on DeepSeek V4-Flash for ALL 131 documents (run id meta_ds).
Same prompt as s34. The 51 Gemini extractions (meta1) remain as a cross-model check."""
import json, os, sys, time, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s34_datasheet_extract import PROMPT, EXTRA, focused   # reuse identical prompt

DS = os.environ["DEEPSEEK_KEY"]
RUN = "meta_ds"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")

docs = sorted(u for u in os.listdir(CORPUS)
              if os.path.exists(os.path.join(CORPUS, u, "llm_run1.json"))
              or os.path.exists(os.path.join(CORPUS, u, "llm_wext.json")))
usage = {"model": "deepseek-v4-flash", "input_tokens": 0, "output_tokens": 0, "calls": 0}
print(f"datasheet (DeepSeek) for {len(docs)} documents", flush=True)
t0 = time.time()
for i, uuid in enumerate(docs):
    d = os.path.join(CORPUS, uuid)
    outp = os.path.join(d, f"llm_{RUN}.json")
    if os.path.exists(outp):
        continue
    gt = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))
    text = focused(open(os.path.join(d, "pdftext.txt"), encoding="utf8").read())
    body = {"model": "deepseek-v4-flash",
            "messages": [{"role": "user", "content":
                          PROMPT.format(name=gt["name"], codes=", ".join(EXTRA), text=text)}],
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
    if (i + 1) % 15 == 0:
        print(f"[{i+1}/{len(docs)}] {(time.time()-t0)/60:.1f} min", flush=True)

cost = usage["input_tokens"] * 0.14e-6 + usage["output_tokens"] * 0.28e-6
usage["cost_usd_est"] = round(cost, 4)
json.dump(usage, open(os.path.join(ROOT, f"usage_{RUN}.json"), "w"), indent=1)
print(f"DONE {usage['calls']} calls, est ${cost:.3f}, {(time.time()-t0)/60:.1f} min", flush=True)
