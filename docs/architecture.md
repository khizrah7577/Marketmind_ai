# MarketMind AI — architecture notes (Deliverable 4)

```
Request
  → Request Analyser (scope + ambiguities/assumptions)
  → Research Planner (schema-validated plan)
  → Research Agent loop (bounded: iterations / tool calls / $)
       ⇄ Tool Dispatcher (validate → authorise → execute → provenance)
       ⇄ Evidence Analyst (accept/flag/reject + epistemic type)
  → Comparison Agent (entity×attribute; not_established cells)
  → Synthesis Agent (findings with evidence_ids)
  → Quality-Control Agent (code mechanical + model contradictions)
       ↺ repair (max 2) with targeted gap questions
  → Report Generator (schema + markdown render)
  → Human Approval Gate (approve | reject | expand | rescope)
  → Published artefact ONLY on approve
```

Every stage writes to `runs/<run_id>/` (plan, tool_log, evidence, qc, report, usage, events, run.log).

## Information source

Curated local corpus under `data/corpus/` (26 documents for S1 AI customer support): vendor pages, pricing, press/analyst notes, planted contradiction (market size $8.2bn vs $5.1bn), planted gap (Capacity enterprise seat minimum), planted prompt-injection document.
