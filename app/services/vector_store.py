from typing import Any, Dict, List, Optional

import chromadb

from app.core.config import settings
from app.services.embeddings import embed

_client = None
_collection = None


def get_collection():
    global _client, _collection

    if _collection is None:
        _client = chromadb.HttpClient(
            host=settings.chromadb_host,
            port=settings.chromadb_port,
        )
        _collection = _client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )

    return _collection


def chromadb_status() -> str:
    try:
        count = get_collection().count()
        return f"ok ({count} dokumentow)"
    except Exception as exc:
        return f"error: {exc}"


def add_document(
    doc_id: str,
    text: str,
    metadata: Dict[str, Any],
) -> None:
    get_collection().add(
        ids=[doc_id],
        embeddings=[embed(text)],
        documents=[text],
        metadatas=[metadata],
    )


def _cosine_similarity(distance: float) -> float:
    """
    Chroma zwraca cosine distance w zakresie [0, 2].
    Podobieństwo cosine wynosi 1 - distance.
    """
    similarity = 1.0 - distance
    return round(max(0.0, min(similarity, 1.0)), 4)


def search_similar(
    query: str,
    top_k: int = 5,
    where: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    collection = get_collection()

    total_documents = collection.count()
    if total_documents == 0:
        return []

    limit = min(top_k, total_documents)

    results = collection.query(
        query_embeddings=[embed(query)],
        n_results=limit,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    output: List[Dict[str, Any]] = []

    for index, document in enumerate(documents):
        metadata = metadatas[index] if index < len(metadatas) else {}
        distance = distances[index] if index < len(distances) else 1.0

        output.append(
            {
                "job_id": metadata.get("job_id", ""),
                "filename": metadata.get("filename", ""),
                "transcription": document,
                "score": _cosine_similarity(distance),
                "created_at": metadata.get("created_at"),
            }
        )

    return output
