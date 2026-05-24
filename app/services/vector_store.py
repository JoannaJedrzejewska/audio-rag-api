from typing import List, Dict, Any
import chromadb
from app.core.config import settings
from app.services.embeddings import embed

_client = None
_collection = None

def get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.HttpClient(host=settings.chromadb_host, port=settings.chromadb_port)
        _collection = _client.get_or_create_collection(
            name=settings.chroma_collection, metadata={"hnsw:space": "cosine"})
    return _collection

def chromadb_status() -> str:
    try:
        return f"ok ({get_collection().count()} dokumentow)"
    except Exception as e:
        return f"error: {e}"

def add_document(doc_id: str, text: str, metadata: Dict[str, Any]) -> None:
    get_collection().add(ids=[doc_id], embeddings=[embed(text)],
                         documents=[text], metadatas=[metadata])

def search_similar(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    col = get_collection()
    if col.count() == 0:
        return []
    results = col.query(query_embeddings=[embed(query)],
                        n_results=min(top_k, col.count()),
                        include=["documents", "metadatas", "distances"])
    output = []
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i]
        output.append({"job_id": meta.get("job_id", ""), "filename": meta.get("filename", ""),
                       "transcription": doc, "score": round(1 - results["distances"][0][i], 4),
                       "created_at": meta.get("created_at")})
    return output
