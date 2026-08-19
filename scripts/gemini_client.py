# -*- coding: utf-8 -*-
"""Rate-limited, key-rotating Gemini client for the free tier.

Free-tier gemini-2.5-flash is roughly 10 requests/min and 250k tokens/min per key,
so with three keys we pace ~1 call every 2.5 s overall and give each key a cooldown.
On 429 (quota) or 503 (capacity) the client parks that key and moves to the next.

usage:
    from gemini_client import GeminiPool
    pool = GeminiPool()                       # reads GEMINI_KEYS (comma separated)
    text, usage = pool.generate(prompt)
"""
import os, time, json, random, requests

MODEL = "gemini-2.5-flash"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
PRICE_IN, PRICE_OUT = 0.30 / 1e6, 2.50 / 1e6   # for reporting only; free tier bills 0


class GeminiPool:
    def __init__(self, keys=None, min_gap_per_key=None, global_gap=None, verbose=True):
        min_gap_per_key = float(os.environ.get("GEMINI_KEY_GAP", min_gap_per_key or 7.0))
        global_gap = float(os.environ.get("GEMINI_GLOBAL_GAP", global_gap or 2.5))
        keys = keys or [k.strip() for k in os.environ.get("GEMINI_KEYS", "").split(",") if k.strip()]
        if not keys:
            raise SystemExit("no keys: set GEMINI_KEYS=key1,key2,key3")
        self.keys = keys
        self.next_ok = {k: 0.0 for k in keys}      # earliest time each key may be used
        self.parked = {k: 0.0 for k in keys}       # cooldown after 429/503
        self.min_gap = min_gap_per_key
        self.global_gap = global_gap
        self.last_call = 0.0
        self.verbose = verbose
        self.usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0,
                      "retries": 0, "key_switches": 0, "by_key": {k[-6:]: 0 for k in keys}}

    def _pick(self):
        now = time.time()
        ready = [k for k in self.keys if max(self.next_ok[k], self.parked[k]) <= now]
        if ready:
            return min(ready, key=lambda k: self.next_ok[k])
        soonest = min(self.keys, key=lambda k: max(self.next_ok[k], self.parked[k]))
        wait = max(self.next_ok[soonest], self.parked[soonest]) - now
        if wait > 0:
            if self.verbose and wait > 3:
                print(f"    [pool] all keys cooling, waiting {wait:.1f}s", flush=True)
            time.sleep(wait)
        return soonest

    def generate(self, prompt, max_output_tokens=16000, thinking_budget=0, max_attempts=12):
        body = {"contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json",
                                     "maxOutputTokens": max_output_tokens,
                                     "thinkingConfig": {"thinkingBudget": thinking_budget}}}
        last_key = None
        for attempt in range(max_attempts):
            key = self._pick()
            if last_key and key != last_key:
                self.usage["key_switches"] += 1
            last_key = key
            gap = self.global_gap - (time.time() - self.last_call)
            if gap > 0:
                time.sleep(gap)
            try:
                r = requests.post(URL, params={"key": key}, json=body, timeout=300)
            except requests.RequestException as e:
                self.usage["retries"] += 1
                self.parked[key] = time.time() + 20
                continue
            self.last_call = time.time()
            self.next_ok[key] = time.time() + self.min_gap
            if r.status_code == 200:
                d = r.json()
                um = d.get("usageMetadata", {})
                self.usage["input_tokens"] += um.get("promptTokenCount", 0)
                self.usage["output_tokens"] += (um.get("candidatesTokenCount", 0)
                                                + um.get("thoughtsTokenCount", 0))
                self.usage["calls"] += 1
                self.usage["by_key"][key[-6:]] += 1
                try:
                    return d["candidates"][0]["content"]["parts"][0]["text"], self.usage
                except (KeyError, IndexError):
                    return None, self.usage
            if r.status_code == 429:
                self.parked[key] = time.time() + 65        # per-minute quota
                self.usage["retries"] += 1
                if self.verbose:
                    print(f"    [pool] 429 on ...{key[-6:]}, parking 65s", flush=True)
                continue
            if r.status_code in (500, 502, 503):
                self.parked[key] = time.time() + 15
                self.usage["retries"] += 1
                continue
            if self.verbose:
                print(f"    [pool] HTTP {r.status_code}: {r.text[:160]}", flush=True)
            self.parked[key] = time.time() + 30
            self.usage["retries"] += 1
        return None, self.usage

    def cost_report(self):
        u = self.usage
        est = u["input_tokens"] * PRICE_IN + u["output_tokens"] * PRICE_OUT
        return {**u, "paid_tier_equivalent_usd": round(est, 4)}


if __name__ == "__main__":
    pool = GeminiPool()
    print(f"pool of {len(pool.keys)} keys; probing each")
    ok = 0
    for i in range(len(pool.keys) * 2):
        t0 = time.time()
        txt, _ = pool.generate('Return ONLY compact JSON {"ok":1}', max_output_tokens=40)
        good = txt is not None
        ok += good
        print(f"  call {i+1}: {'OK' if good else 'FAIL'} ({time.time()-t0:.1f}s) -> {str(txt)[:40]}")
    print(f"\n{ok}/{len(pool.keys)*2} succeeded")
    print("usage:", json.dumps(pool.cost_report(), indent=1))
