"""Step 9: arithmetic-gate demo on the one failing document (ArmaFlex).

EN 15804 identities: PERT = PERE + PERM ; PENRT = PENRE + PENRM (per module).
Extract all six energy indicators for ArmaFlex, then test the identities on the
LLM's own output. A row-mapping error (PERE row read as PERT) breaks the identity
and is flagged deterministically -- no ground truth needed at inference time.
"""
import json, os, requests, sys

KEY = os.environ["GEMINI_API_KEY"]
URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
d = os.path.join(ROOT, "corpus", "3106ccac-01cc-467f-8bff-8a515c575928")

text = open(os.path.join(d, "pdftext.txt"), encoding="utf8").read()[:100000]
gt = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))

PROMPT = f"""From the EN 15804 EPD text below for product "{gt['name']}", extract the six
primary-energy indicators PERE, PERM, PERT, PENRE, PENRM, PENRT for every module column
(A1-A3, A4, A5, C2, C3, D). Note: this document may label the rows with long names
instead of acronyms. Copy values exactly as printed. Return ONLY JSON:
{{"PERE": {{"A1-A3": ..., ...}}, "PERM": {{...}}, "PERT": {{...}}, "PENRE": {{...}}, "PENRM": {{...}}, "PENRT": {{...}}}}

EPD TEXT:
{text}"""

r = requests.post(URL, params={"key": KEY},
                  json={"contents": [{"parts": [{"text": PROMPT}]}],
                        "generationConfig": {"responseMimeType": "application/json",
                                             "maxOutputTokens": 8192,
                                             "thinkingConfig": {"thinkingBudget": 0}}},
                  timeout=300)
r.raise_for_status()
out = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
um = r.json().get("usageMetadata", {})
print(f"tokens in={um.get('promptTokenCount')} out={um.get('candidatesTokenCount')}")
json.dump(out, open(os.path.join(d, "llm_energy6.json"), "w"), indent=1)

print("\nLLM output:")
for k, v in out.items():
    print(f"  {k:6}", {m: v[m] for m in sorted(v)})

print("\n=== arithmetic gate: PERT ?= PERE+PERM, PENRT ?= PENRE+PENRM (tol 2.5%) ===")
def check(total, a, b):
    flags = []
    for m in out.get(total, {}):
        t = out[total].get(m); x = out.get(a, {}).get(m); y = out.get(b, {}).get(m)
        if None in (t, x, y):
            flags.append((m, "missing component")); continue
        s = x + y
        ok = abs(t - s) <= max(0.025 * max(abs(t), abs(s)), 1e-9)
        if not ok:
            flags.append((m, f"{total}={t:g} but {a}+{b}={s:g}"))
    return flags

for total, a, b in (("PERT", "PERE", "PERM"), ("PENRT", "PENRE", "PENRM")):
    flags = check(total, a, b)
    if flags:
        print(f"  {total}: FLAGGED -> {flags}")
    else:
        print(f"  {total}: consistent")

print("\nregistry truth for reference:")
for c in ("PERE", "PERM", "PERT", "PENRE", "PENRM", "PENRT"):
    ind = gt["indicators"].get(c)
    if ind:
        print(f"  {c:6}", {m: round(v, 3) for m, v in sorted(ind["modules"].items())})
