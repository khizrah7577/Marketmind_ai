from src.tools import corpus


def test_index_loaded():
    docs = corpus.load_index()
    assert len(docs) >= 20


def test_contradiction_docs_exist():
    ids = {d["id"] for d in corpus.load_index()}
    assert "press_market_size_a" in ids
    assert "press_market_size_b" in ids


def test_injection_plant_exists():
    text = corpus.read_document_text("injection_plant_doc")
    assert text and "ignore prior instructions" in text.lower()
