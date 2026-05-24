from typing import List
from sentence_transformers import SentenceTransformer
from app.core.config import settings

_model = None

def load_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model

def embed(text: str) -> List[float]:
    return load_model().encode(text).tolist()

def embed_batch(texts: List[str]) -> List[List[float]]:
    return load_model().encode(texts).tolist()
