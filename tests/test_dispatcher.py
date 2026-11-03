from src.state.research_state import ResearchState
from src.tools.dispatcher import ToolDispatcher
from src.tools.registry import build_default_registry


def test_unknown_tool():
    st = ResearchState(run_id="t")
    d = ToolDispatcher(build_default_registry(), st)
    r = d.dispatch("nope", {})
    assert r["error"] == "unknown_tool"


def test_schema_bounds():
    st = ResearchState(run_id="t")
    d = ToolDispatcher(build_default_registry(), st)
    r = d.dispatch(
        "search_information",
        {"query": "pricing", "source_type": "pricing", "max_results": 99},
    )
    assert r["error"] == "schema_validation"


def test_save_requires_source():
    st = ResearchState(run_id="t")
    d = ToolDispatcher(build_default_registry(), st)
    r = d.dispatch(
        "save_research",
        {
            "question_id": "q1",
            "claim": "Something invented",
            "claim_type": "fact",
            "source_ref": "missing",
            "confidence": "high",
        },
    )
    assert r["error"] == "unresolvable_source_ref"


def test_search_returns_list():
    st = ResearchState(run_id="t")
    d = ToolDispatcher(build_default_registry(), st)
    r = d.dispatch(
        "search_information",
        {"query": "Zendesk", "source_type": "any", "max_results": 5},
    )
    assert r["ok"] is True
    assert isinstance(r["hits"], list)
