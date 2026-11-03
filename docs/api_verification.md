# API verification log (Deliverable 11)

**Verified against:** OpenAI API reference (platform.openai.com/docs)  
**Date verified:** 2026-10-30  
**SDK:** `openai` Python SDK ≥1.54 (Chat Completions)

## Confirmed patterns used in this build

| Capability | Pattern used | Notes |
|---|---|---|
| Chat completions | `client.chat.completions.create(...)` | Primary surface |
| Tools / function calling | `tools=[{type:function, function:{name,description,parameters}}]` | Arguments arrive as JSON **strings** |
| Parallel tool calls | Multiple entries in `message.tool_calls` | Dispatched sequentially in our loop; results returned as `role=tool` |
| Structured outputs | `response_format={type:json_schema, json_schema:{name,strict:true,schema}}` | Local Pydantic/jsonschema validation still required |
| Models | Default `gpt-4o-mini` per stage via env | Override with `MODEL_*` |
| Rate limits | `RateLimitError` → exponential backoff + jitter | Distinct from auth / timeout / context_length |
| Timeouts | Client `timeout=` + our retry loop | |

## Deliberate non-use

- No Assistants API / Threads (assignment requires a custom loop).
- No third-party agent executor (LangChain agents, Swarm orchestration, etc.).
- Responses API not required for this submission; Chat Completions + tools + json_schema is sufficient and documented.

## Pricing assumptions

Token USD estimates in `src/llm/usage.py` are approximate for cost ceilings and must be treated as engineering controls, not invoices.
