# -*- coding: utf-8 -*-
"""Connectivity + capability test for DeepSeek and the new free-tier Gemini key.
Checks: auth, JSON mode, context size handling, usage reporting."""
import os, json, requests, time

DS = os.environ["DEEPSEEK_KEY"]
GM = os.environ["GEMINI_KEY"]
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "corpus")

# a real focused input from the corpus, same as the paper's workflow config
uuid = "c54c16f6-4295-4749-bff0-ba7ed4bc9117"  # LinCrete
text = open(os.path.join(ROOT, uuid, "pdftext.txt"), encoding="utf8").read()
low = text.lower()
idx = low.find("results of the lca")
focused = text[:4000] + "\n[...]\n" + (text[idx:idx + 32000] if idx >= 0 else text[:32000])
print(f"focused input: {len(focused)} chars (~{len(focused)//4} tokens)")

PROMPT = ("From this EN 15804 EPD, return ONLY JSON: "
          '{"declared_unit": "...", "gwp_total_a1a3": <number>} '
          "for the product 'LinCrete' Glass-Fibre Reinforced Concrete.\n\n" + focused)

print("\n=== DEEPSEEK (deepseek-chat) ===")
t0 = time.time()
try:
    r = requests.post("https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {DS}", "Content-Type": "application/json"},
        json={"model": "deepseek-chat",
              "messages": [{"role": "user", "content": PROMPT}],
              "response_format": {"type": "json_object"},
              "temperature": 0, "max_tokens": 2000},
        timeout=300)
    print("status:", r.status_code, f"({time.time()-t0:.1f}s)")
    if r.ok:
        d = r.json()
        print("output:", d["choices"][0]["message"]["content"][:300])
        print("usage:", d.get("usage"))
    else:
        print("error:", r.text[:400])
except Exception as e:
    print("EXCEPTION:", repr(e)[:300])

print("\n=== GEMINI (new free-tier key, gemini-2.5-flash) ===")
t0 = time.time()
try:
    r = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        params={"key": GM},
        json={"contents": [{"parts": [{"text": PROMPT}]}],
              "generationConfig": {"responseMimeType": "application/json",
                                   "maxOutputTokens": 2000,
                                   "thinkingConfig": {"thinkingBudget": 0}}},
        timeout=300)
    print("status:", r.status_code, f"({time.time()-t0:.1f}s)")
    if r.ok:
        d = r.json()
        try:
            print("output:", d["candidates"][0]["content"]["parts"][0]["text"][:300])
        except Exception:
            print("no parts:", json.dumps(d)[:300])
        print("usage:", d.get("usageMetadata"))
    else:
        print("error:", r.text[:400])
except Exception as e:
    print("EXCEPTION:", repr(e)[:300])

print("\n=== registry truth for comparison ===")
gt = json.load(open(os.path.join(ROOT, uuid, "gt.json"), encoding="utf8"))
print("GWP-total A1-A3:", gt["indicators"]["GWP-total"]["modules"]["A1-A3"])
