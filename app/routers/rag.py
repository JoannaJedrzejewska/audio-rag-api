import logging
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status

from app.schemas.models import (
    AnswerRequest,
    AnswerResponse,
    AnswerSource,
    SearchRequest,
    SearchResultItem,
    SearchResponse,
)
from app.services.llm import generate_answer
from app.services.vector_store import search_similar

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rag", tags=["rag"])


MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def extract_date_filter(question: str) -> Optional[Dict[str, Any]]:
    """
    Wykrywa wyrażenie typu 'June 2025' i zwraca filtr ChromaDB.
    Obsługuje również polskie nazwy miesięcy.
    """
    question_lower = question.lower()

    english_match = re.search(
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})\b",
        question_lower,
    )

    if english_match:
        month_name, year = english_match.groups()
        month = MONTHS[month_name]
        return _build_month_filter(int(year), month)

    polish_months = {
        "stycznia": 1,
        "lutego": 2,
        "marca": 3,
        "kwietnia": 4,
        "maja": 5,
        "czerwca": 6,
        "lipca": 7,
        "sierpnia": 8,
        "września": 9,
        "października": 10,
        "listopada": 11,
        "grudnia": 12,
    }

    polish_match = re.search(
        r"\b(stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|września|października|listopada|grudnia)\s+(\d{4})\b",
        question_lower,
    )

    if polish_match:
        month_name, year = polish_match.groups()
        month = polish_months[month_name]
        return _build_month_filter(int(year), month)

    return None


def _build_month_filter(year: int, month: int) -> Dict[str, Any]:
    return {
        "$and": [
            {"year": {"$eq": year}},
            {"month": {"$eq": month}},
        ]
    }


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Wyszukiwanie semantyczne wśród transkrypcji",
)
def rag_search(body: SearchRequest):
    try:
        date_filter = extract_date_filter(body.query)

        hits = search_similar(
            query=body.query,
            top_k=body.top_k,
            where=date_filter,
        )

        if not hits and date_filter is not None:
            logger.info(
                "Brak wyników dla filtra daty; wykonuję wyszukiwanie bez filtra."
            )
            hits = search_similar(
                query=body.query,
                top_k=body.top_k,
            )

    except Exception:
        logger.exception("Błąd podczas wyszukiwania semantycznego.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Nie udało się wykonać wyszukiwania. Spróbuj ponownie później.",
        )

    results = [SearchResultItem(**hit) for hit in hits]

    return SearchResponse(
        query=body.query,
        results=results,
        total_found=len(results),
    )


@router.post(
    "/answer",
    response_model=AnswerResponse,
    summary="Pytanie do bazy transkrypcji z odpowiedzią LLM",
)
def rag_answer(body: AnswerRequest):
    try:
        date_filter = extract_date_filter(body.question)

        contexts = search_similar(
            query=body.question,
            top_k=body.top_k,
            where=date_filter,
        )

        if not contexts and date_filter is not None:
            logger.info(
                "Brak kontekstu dla filtra daty; wykonuję retrieval bez filtra."
            )
            contexts = search_similar(
                query=body.question,
                top_k=body.top_k,
            )

    except Exception:
        logger.exception("Błąd podczas retrievalu.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Nie udało się wyszukać kontekstu. Spróbuj ponownie później.",
        )

    if not contexts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brak transkrypcji w bazie. Prześlij najpierw nagrania audio.",
        )

    try:
        answer, model_used = generate_answer(body.question, contexts)
    except ValueError as exc:
        logger.error("Niepoprawna konfiguracja LLM: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Usługa generowania odpowiedzi jest obecnie niedostępna.",
        )
    except Exception:
        logger.exception("Błąd podczas generowania odpowiedzi przez LLM.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Nie udało się wygenerować odpowiedzi. Spróbuj ponownie później.",
        )

    sources = [
        AnswerSource(
            job_id=context["job_id"],
            filename=context["filename"],
            excerpt=context["transcription"][:300],
        )
        for context in contexts
    ]

    return AnswerResponse(
        question=body.question,
        answer=answer,
        sources=sources,
        model_used=model_used,
    )
