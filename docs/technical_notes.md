# Technical notes

## Per-stage temperatures (Task 02)

| Stage | Temperature | Rationale |
|---|---|---|
| Analyser | 0.2 | Deterministic scope extraction |
| Planner | 0.3 | Some diversity in questions, still structured |
| Researcher | 0.2 | Tool selection should be stable |
| Evidence | 0.1 | Extraction, not creativity |
| Comparison | 0.1 | Matrix fidelity |
| Synthesis | 0.4 | Readable narrative under evidence constraints |
| QC | 0.1 | Diagnostic consistency |
| Report | 0.3 | Prose quality without invention |

Run `python -m src.main show-messages` and a manual dual-temperature experiment; record variance in your viva notebook. Higher temperature increased paraphrase variance on the same planner prompt in smoke checks; low temperature preferred for extraction stages.

## Schema vs truth (Task 03)

1. **Valid JSON** — parses.  
2. **Schema-valid** — matches JSON Schema / Pydantic.  
3. **Correct** — claims match sources.  

Example failure mode: a schema-valid plan can still contain a vague sub-question; our code validator rejects unbounded wording. A schema-valid report can still fabricate — blocked by `source_ref` resolution at `save_research`.

## Tool abuse one-liners (Section 5.4)

| Tool | Abuse if unconstrained | Mitigation |
|---|---|---|
| search_information | Huge max_results / injection via query | max_results ≤ 20; corpus-only |
| retrieve_document | Path traversal / arbitrary URL fetch | Exact index id; reject `/`, `..`, `http` |
| calculate_metric | Arbitrary code via expression | Closed operation enum; Python arithmetic only |
| compare_companies | Huge entity lists | Array length caps; evidence-only cells |
| save_research | Fabricated citations | `source_ref` must resolve |
| generate_report | Publish bypass | Does not publish; approval gate separate |

## Rescope retention rule (Task 09)

On modify-scope: **retain prior evidence by default** (vendor/pricing facts usually remain valid under geography/segment narrowing). If the amendment contains `exclude`, drop evidence matching excluded tokens. Justified because re-fetching unchanged corpus facts wastes budget without improving truthfulness.

## Primary scenario

**S1 — AI customer support software.** Planner also exercised conceptually on S2 (coding assistants) and S4 (enterprise RAG) shapes in documentation for Task 04.
