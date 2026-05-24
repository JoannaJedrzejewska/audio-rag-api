import logging
from fastapi import APIRouter, HTTPException, status

from app.schemas.models import (
    SearchRequest, SearchResponse, SearchResultItem,
    AnswerRequest, AnswerResponse, AnswerSource,
)
from app.services.vector_store import search_similar
from app.services.llm import generate_answer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rag", tags=["rag"])


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Wyszukiwanie semantyczne wśród transkrypcji",
)
def rag_search(body: SearchRequest):
    try:
        hits = search_similar(body.query, top_k=body.top_k)
    except Exception as e:
        logger.error("Błąd wyszukiwania: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Błąd wyszukiwania: {e}",
        )

    results = [SearchResultItem(**h) for h in hits]
    return SearchResponse(
        query=body.query,
        results=results,
        total_found=len(results),
    )


@router.post(
    "/answer",
    response_model=AnswerResponse,
    summary="Pytanie do bazy transkrypcji",
)
def rag_answer(body: AnswerRequest):
    try:
        contexts = search_similar(body.question, top_k=body.top_k)
    except Exception as e:
        logger.error("Błąd retrievalu: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Błąd retrievalu: {e}",
        )

    if not contexts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brak transkrypcji w bazie — prześlij najpierw nagrania audio.",
        )

    try:
        answer, model_used = generate_answer(body.question, contexts)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Błąd LLM: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Błąd generowania odpowiedzi: {e}",
        )

    sources = [
        AnswerSource(
            job_id=c["job_id"],
            filename=c["filename"],
            excerpt=c["transcription"][:300],
        )
        for c in contexts
    ]

    return AnswerResponse(
        question=body.question,
        answer=answer,
        sources=sources,
        model_used=model_used,
    )
