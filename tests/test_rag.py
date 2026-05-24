import pytest
from unittest.mock import patch


def test_search_returns_results(client):
    r = client.post("/rag/search", json={"query": "stopy procentowe", "top_k": 3})
    assert r.status_code == 200
    body = r.json()
    assert "results" in body
    assert "total_found" in body
    assert body["query"] == "stopy procentowe"


def test_search_validates_short_query(client):
    r = client.post("/rag/search", json={"query": "x"})
    assert r.status_code == 422


def test_search_validates_top_k(client):
    r = client.post("/rag/search", json={"query": "inflacja", "top_k": 999})
    assert r.status_code == 422


def test_answer_local_provider(client):
    r = client.post("/rag/answer", json={"question": "Jaka była stopa w marcu 2024?", "top_k": 3})
    assert r.status_code == 200
    body = r.json()
    assert "answer" in body
    assert "sources" in body
    assert "model_used" in body


def test_answer_missing_question(client):
    r = client.post("/rag/answer", json={"question": "Hi"})
    assert r.status_code == 422


def test_search_result_schema(client):
    r = client.post("/rag/search", json={"query": "inflacja EBC", "top_k": 2})
    assert r.status_code == 200
    for item in r.json()["results"]:
        assert "job_id"        in item
        assert "filename"      in item
        assert "transcription" in item
        assert "score"         in item
        assert 0.0 <= item["score"] <= 1.0