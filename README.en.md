# Hunting Workflow

Offline asset normalization and evidence-driven vulnerability report preparation.
Python 3.9+, no third-party runtime dependencies, no accounts or real targets required.

```sh
git clone https://github.com/MosEcho/hunting-workflow.git
cd hunting-workflow
python3 run.py demo --output out/demo
```

Read `out/demo/START-HERE.md`, then open `out/demo/complete/report.html` in a browser.
The demo turns six inventory rows into four services and produces a complete synthetic report,
CNNVD draft fields, evidence references, a missing-material checklist and a standalone ZIP.
A second, deliberately incomplete case demonstrates the gaps to resolve.

All example products, contacts, requests, responses, screenshots, searches and reviewer records are fabricated.
Synthetic cases remain blocked from real submission even when their material structure is complete.

## Commands

```sh
python3 run.py assets normalize examples/assets.csv --output out/assets
python3 run.py case check examples/complete-case/case.json --json
python3 run.py case build examples/complete-case/case.json --output out/case
python3 run.py case export out/case --output out/review.zip
```

The example `case check` exits with **2**, intentionally: it is synthetic and live platform rules are unconfirmed.
Successful draft generation exits with 0, independently of readiness. Use a new output directory on each run.
Optional installation: `python3 -m pip install .`, then use `hunting-workflow`.

## What gets checked

- Inventory endpoint normalization, service deduplication, source rows and identity claims.
- Case structure, local evidence paths, SHA-256, claim references, versions, scope records and missing materials.
- Explicit human verification, originality comparison records and self-rating rationale.
- Synthetic markers and an explicit human confirmation of current platform requirements.

These checks do not establish vulnerability validity, real authorization, originality or platform acceptance.
The CNNVD profile is drafting guidance, not an official specification; no fixed instance count or certificate guarantee is encoded.
The runtime performs no target requests, scans, exploit execution or submission API calls.

## Develop

```sh
python3 -m unittest discover -s tests -v
python3 tools/check_docs.py
python3 tools/audit_public.py
```

[Chinese guide](README.md) · [CLI](docs/cli.md) · [Data model](docs/data-model.md) · [Methods](docs/methodology.md) · [Publication](docs/publication.md)

Original project code and synthetic materials are provided under the [MIT license](LICENSE).
