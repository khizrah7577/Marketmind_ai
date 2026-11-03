from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.state.research_state import ResearchState

# Simple keyword heuristics to fill cells only from evidence claims
ATTR_KEYWORDS: dict[str, list[str]] = {
    "pricing_entry": ["$", "price", "pricing", "/month", "per agent", "per seat", "per user"],
    "pricing_enterprise": ["enterprise", "custom quote", "sales-assisted", "sales assisted"],
    "target_segment": ["smb", "mid-market", "mid market", "enterprise", "ecommerce", "segment"],
    "ai_capability": ["ai ", "generative", "agent", "automation", "einstein", "fin ", "freddy"],
    "channels": ["email", "chat", "voice", "messaging", "omnichannel", "social"],
    "integrations": ["integration", "salesforce", "shopify", "slack", "hubspot", "zendesk"],
    "funding": ["funding", "publicly listed", "private ownership", "valuation"],
    "hq": ["hq:", "headquarter", "san francisco", "toronto", "dublin", "new york"],
    "market_share_claim": ["market share", "% market"],
}


def handle(
    entities: list[str],
    attributes: list[str],
    state: "ResearchState | None" = None,
    **_: Any,
) -> dict[str, Any]:
    matrix = []
    for entity in entities:
        el = entity.lower()
        for attr in attributes:
            cell = {
                "entity": entity,
                "attribute": attr,
                "value": None,
                "status": "not_established",
                "evidence_ids": [],
            }
            if state is None:
                matrix.append(cell)
                continue
            keys = ATTR_KEYWORDS.get(attr, [attr])
            for ev in state.evidence:
                claim_l = ev.claim.lower()
                detail_l = (ev.source_detail or "").lower()
                if el not in claim_l and el not in detail_l and el not in ev.claim.lower():
                    # also match vendor name tokens loosely
                    if not any(tok and tok in claim_l for tok in el.split() if len(tok) > 2):
                        continue
                if any(k in claim_l for k in keys):
                    cell["value"] = ev.claim
                    cell["status"] = "established"
                    cell["evidence_ids"].append(ev.evidence_id)
                    break
            matrix.append(cell)
    return {"ok": True, "matrix": matrix, "entities": entities, "attributes": attributes}
