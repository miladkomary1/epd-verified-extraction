"""Step 16: strict-schema ablation — same task, but enforced via responseSchema.
Runs on the first 6 core documents only (budget). Records acceptance/rejection and,
if accepted, scores via llm_strict.json.
"""
import json, os, sys, time, requests

KEY = os.environ["GEMINI_API_KEY"]
URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")

INDICATORS = ["GWP-total", "GWP-fossil", "GWP-biogenic", "GWP-luluc", "ODP", "AP",
              "EP-freshwater", "EP-marine", "EP-terrestrial", "POCP", "ADPE", "ADPF", "WDP",
              "PERE", "PERM", "PERT", "PENRE", "PENRM", "PENRT",
              "SM", "RSF", "NRSF", "FW", "HWD", "NHWD", "RWD"]
MODULES = ["A1-A3", "A1", "A2", "A3", "A4", "A5", "B1", "B2", "B3", "B4", "B5", "B6", "B7",
           "C1", "C2", "C3", "C4", "D"]

# full nested schema: 26 indicators x (unit + 18 module properties) ~ 500 properties
mod_props = {m: {"type": "number", "nullable": True} for m in MODULES}
ind_schema = {"type": "object",
              "properties": {"unit": {"type": "string"},
                             "values": {"type": "object", "properties": mod_props}}}
SCHEMA = {"type": "object",
          "properties": {"declared_unit": {"type": "string"},
                         "indicators": {"type": "object",
                                        "properties": {c: ind_schema for c in INDICATORS}}}}

MARKERS = ["RESULTS OF THE LCA", "ERGEBNISSE DER ÖKOBILANZ", "LCA: Results"]
def focused(text):
    head = text[:4000]; low = text.lower()
    idx = min((low.find(m.lower()) for m in MARKERS if low.find(m.lower()) >= 0), default=-1)
    return head + "\n[...]\n" + text[idx:idx + 32000] if idx >= 0 else text[:60000]

PROMPT = """Extract from this EN 15804 EPD for product "{name}": the declared unit and, for each EN 15804 indicator code present ({codes}), the printed value for every life-cycle module column. Rows may use long names instead of acronyms. Copy values exactly as printed; never compute.\n\nEPD TEXT:\n{text}"""

core18 = sorted(u for u in os.listdir(CORPUS)
                if os.path.exists(os.path.join(CORPUS, u, "llm_run1.json")))[:6]
usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
outcome = {"schema_properties": 26 * 19 + 2, "rejected": 0, "accepted": 0, "errors": []}

for uuid in core18:
    d = os.path.join(CORPUS, uuid)
    gt = json.load(open(os.path.join(d, "gt.json"), encoding="utf8"))
    text = focused(open(os.path.join(d, "pdftext.txt"), encoding="utf8").read())
    body = {"contents": [{"parts": [{"text": PROMPT.format(name=gt["name"], codes=", ".join(INDICATORS), text=text)}]}],
            "generationConfig": {"responseMimeType": "application/json",
                                 "responseSchema": SCHEMA,
                                 "maxOutputTokens": 16384,
                                 "thinkingConfig": {"thinkingBudget": 0}}}
    r = requests.post(URL, params={"key": KEY}, json=body, timeout=300)
    if not r.ok:
        outcome["rejected"] += 1
        outcome["errors"].append({"uuid": uuid, "status": r.status_code, "msg": r.text[:300]})
        print(uuid[:8], "REJECTED", r.status_code, r.text[:160].replace("\n", " "))
        continue
    dj = r.json()
    um = dj.get("usageMetadata", {})
    usage["input_tokens"] += um.get("promptTokenCount", 0)
    usage["output_tokens"] += um.get("candidatesTokenCount", 0) + um.get("thoughtsTokenCount", 0)
    usage["cost_usd"] = usage["input_tokens"] * 0.3e-6 + usage["output_tokens"] * 2.5e-6
    try:
        txt = dj["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(txt)
        json.dump(parsed, open(os.path.join(d, "llm_strict.json"), "w", encoding="utf8"),
                  ensure_ascii=False, indent=1)
        outcome["accepted"] += 1
        print(uuid[:8], "accepted, indicators:", len(parsed.get("indicators") or {}),
              f"finish={dj['candidates'][0].get('finishReason')}")
    except Exception as e:
        outcome["errors"].append({"uuid": uuid, "parse": repr(e)[:200],
                                  "finish": dj.get("candidates", [{}])[0].get("finishReason")})
        print(uuid[:8], "output error:", repr(e)[:120])
    time.sleep(1)

outcome["usage"] = usage
json.dump(outcome, open(os.path.join(ROOT, "strict_schema_outcome.json"), "w"), indent=1)
print(outcome["rejected"], "rejected /", outcome["accepted"], "accepted; cost", usage["cost_usd"])
