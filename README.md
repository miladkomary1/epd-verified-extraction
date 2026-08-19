# Registry-verified extraction of EPD impact indicators

Workflow, data and figures for the paper *Registry-verified extraction of environmental
product declaration impact indicators using large language models for the digitalization
of construction sustainability data*.

Environmental product declarations (EPDs) publish EN 15804+A2 life-cycle impact
indicators as PDF tables. This repository extracts those tables and, more importantly,
**screens every extracted value with two deterministic checks** before surfacing it:

1. **Source grounding.** A value is surfaced only if one of the ways a number of that
   magnitude is printed in EPD tables occurs verbatim in the normalized document text.
2. **Arithmetic identity.** The additivity relations the standard imposes are tested on
   the model's own output: `PERT = PERE + PERM`, `PENRT = PENRE + PENRM`, and
   `GWP-total = GWP-fossil + GWP-biogenic + GWP-luluc`.

A value that fails either check is withheld rather than reported. Evaluation is
*registry-referenced*: the machine-readable records of the OEKOBAUDAT registry supply the
reference values, so thousands of indicator slots are scored without new manual
annotation. The same screen is then turned on the registry itself, as an audit of how far
its records can be traced to the documents they cite.

## Quick start

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...            # only for the language-model path
python scripts/s4_collect_corpus.py  # rebuild the corpus from the public registry
python scripts/s15_det_parser.py     # deterministic parser, no key and no cost
python scripts/s13_extract_w.py      # language-model extraction
python scripts/s8_grounding_gate.py  # source-grounding check
python scripts/s9b_arith_check.py    # arithmetic identity check
python scripts/s14_score.py          # score against the registry records
```

Scripts are numbered in execution order. Every API key is read from the environment;
none is stored in this repository.

## What is here

| Path | Contents |
|---|---|
| `scripts/` | The pipeline, in execution order, from collection to figures. |
| `data/` | Corpus manifest, per-run evaluation and usage records, the registry-wide scan, the exports. |
| `figures/` | Manuscript and supplementary figures, 400 dpi PNG, as published. |

Files worth knowing about:

- `data/corpus_manifest.csv` : registry identifier, product name, category and source URL
  of every declaration used. The PDFs are **not** redistributed; this manifest lets the
  corpus be rebuilt from the public registry.
- `data/fullstock_scan.jsonl` : one record per process dataset in the 2024 data stock,
  with document availability and the outcome of the record-document screen.
- `data/okobaudat_real_export.csv` : verified output written in the published OEKOBAUDAT
  column layout (semicolon separated, ISO-8859-1, 100 columns, one row per product and
  life-cycle module).
- `scripts/s38_verify_okobaudat_export.py` : the compatibility proof. Compares the
  generated header cell by cell with a published export, appends every generated row to
  it, and re-parses the combined file.

## What is not here

- **The declaration PDFs.** They belong to their programme operators. Use the manifest.
- **The web application.** An interactive tool built on this workflow runs at
  <https://epd-llm.miladkomary.com>. Its front end and back end are not part of this release.

## Citing

See `CITATION.cff`. Please cite the paper and this archive.

## Licence

Code in `scripts/` is released under the MIT Licence (`LICENSE`). The contents of `data/`
and `figures/` are released under CC BY 4.0 (`LICENSE-DATA`).
