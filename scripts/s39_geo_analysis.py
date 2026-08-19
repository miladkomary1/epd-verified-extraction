# -*- coding: utf-8 -*-
"""Characterise the geography disagreements defensibly.

Hypothesis: the registry stores the dataset's geographic REPRESENTATIVENESS
(supra-national codes RER/GLO), while the declaration states the manufacturing
LOCATION (a specific country). Test: among disagreements, how many have a
supra-national registry code against a specific extracted country?
"""
import json, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(ROOT, "corpus")
SUPRA = {"RER", "GLO", "EU", "EU-27", "RNA", "RAS", "RAF"}
COUNTRY = {
 "US": ["US", "USA", "UNITED STATES"], "GB": ["GB", "UK", "UNITED KINGDOM"],
 "DE": ["DE", "GERMANY", "DEUTSCHLAND"], "CH": ["CH", "SWITZERLAND", "SCHWEIZ"],
 "AT": ["AT", "AUSTRIA"], "BE": ["BE", "BELGIUM"], "FR": ["FR", "FRANCE"],
 "IT": ["IT", "ITALY"], "ES": ["ES", "SPAIN"], "NL": ["NL", "NETHERLANDS"],
 "PL": ["PL", "POLAND"], "SE": ["SE", "SWEDEN"], "DK": ["DK", "DENMARK"],
 "NO": ["NO", "NORWAY"], "FI": ["FI", "FINLAND"], "CZ": ["CZ", "CZECH"],
 "MX": ["MX", "MEXICO"], "CN": ["CN", "CHINA"], "IE": ["IE", "IRELAND"],
 "PT": ["PT", "PORTUGAL"], "TR": ["TR", "TURKEY"], "GR": ["GR", "GREECE"],
 "HU": ["HU", "HUNGARY"], "RO": ["RO", "ROMANIA"], "SK": ["SK", "SLOVAKIA"],
 "SI": ["SI", "SLOVENIA"], "HR": ["HR", "CROATIA"], "LU": ["LU", "LUXEMBOURG"],
 "RER": ["RER", "EUROPE", "EUROPEAN UNION", "EUROPA"],
 "GLO": ["GLO", "GLOBAL", "WORLDWIDE"],
}
run = os.environ.get("META_RUN", "meta_ds")

agree = supra_vs_country = country_vs_country = empty = other = 0
examples = []
for u in sorted(os.listdir(CORPUS)):
    p = os.path.join(CORPUS, u, f"llm_{run}.json")
    if not os.path.exists(p):
        continue
    pj = json.load(open(os.path.join(CORPUS, u, "registry.json"), encoding="utf8"))
    reg = (pj.get("processInformation", {}).get("geography", {})
           .get("locationOfOperationSupplyOrProduction", {}).get("location"))
    if not reg:
        continue
    got = (json.load(open(p, encoding="utf8")).get("geography") or "").strip()
    r = reg.upper(); gu = got.upper()
    if got and any(re.search(rf"\b{re.escape(a)}\b", gu) for a in COUNTRY.get(r, [r])):
        agree += 1
    elif not got:
        empty += 1
    elif r in SUPRA:
        # registry holds a supra-national scope; is the extraction a specific country?
        hit = [c for c, al in COUNTRY.items()
               if c not in SUPRA and any(re.search(rf"\b{re.escape(a)}\b", gu) for a in al)]
        if hit:
            supra_vs_country += 1
            if len(examples) < 6:
                examples.append((r, got[:22]))
        else:
            other += 1
    else:
        country_vs_country += 1
        if len(examples) < 8:
            examples.append((r, got[:22]))

tot = agree + supra_vs_country + country_vs_country + empty + other
S = {"total": tot, "agree": agree, "supra_vs_country": supra_vs_country,
     "country_vs_country": country_vs_country, "empty": empty, "other": other,
     "examples": examples}
print(json.dumps(S, indent=1, ensure_ascii=False))
print(f"\nagreement {agree}/{tot} = {agree/tot*100:.1f}%")
print(f"registry supra-national scope vs extracted manufacturing country: "
      f"{supra_vs_country} ({supra_vs_country/tot*100:.1f}%)")
print(f"explained (agree + semantic scope difference): "
      f"{(agree+supra_vs_country)/tot*100:.1f}%")
json.dump(S, open(os.path.join(ROOT, "geo_analysis.json"), "w"), indent=1)
