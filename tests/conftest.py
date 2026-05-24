import sys
from unittest.mock import MagicMock

sys.modules["sentence_transformers"] = MagicMock()
sys.modules["faster_whisper"] = MagicMock()
sys.modules["chromadb"] = MagicMock()

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

import app.services.vector_store
import app.services.transcription
import app.services.embeddings


@pytest.fixture(scope="session", autouse=True)
def mock_heavy_models():
    whisper_mock = MagicMock()
    whisper_mock.transcribe.return_value = ([], MagicMock())

    emb_mock = MagicMock()
    emb_mock.encode.return_value = [0.0] * 384

    with (
        patch("faster_whisper.WhisperModel", return_value=whisper_mock),
        patch("sentence_transformers.SentenceTransformer", return_value=emb_mock),
    ):
        yield


@pytest.fixture(scope="session")
def chroma_mock():
    col = MagicMock()
    col.count.return_value = 1
    col.query.return_value = {
        "documents": [["ECB decided to keep rates unchanged."]],
        "metadatas": [[{"job_id": "test-job", "filename": "test.wav", "created_at": "2024-03-07T14:00:00"}]],
        "distances": [[0.1]],
    }
    return col

@pytest.fixture(scope="session")
def client(chroma_mock):
    with patch.object(app.services.vector_store, "get_collection", return_value=chroma_mock):
        from app.main import app as fastapi_app
        with TestClient(fastapi_app, raise_server_exceptions=False) as c:
            yield c