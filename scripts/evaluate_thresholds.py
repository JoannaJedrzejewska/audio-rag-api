import argparse
from collections.abc import Sequence
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SEARCH_LIMIT = 20
THRESHOLDS = [0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25]

# Expected source filename prefixes must match transcripts indexed in ChromaDB.
GOLD_SET = [
    {
        "query": "Jaką decyzję dotyczącą polityki pieniężnej ogłosił EBC 17 kwietnia 2025?",
        "expected_sources": ["20250416_"],
    },
    {
        "query": "Jaką decyzję dotyczącą polityki pieniężnej ogłosił EBC 10 września 2026?",
        "expected_sources": ["20260909_"],
    },
]


def retrieve(query: str, api_url: str, top_k: int = SEARCH_LIMIT) -> list[dict[str, Any]]:
    request = Request(
        f"{api_url.rstrip('/')}/rag/search",
        data=json.dumps({"query": query, "top_k": top_k}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API zwróciło HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Nie można połączyć się z API: {error.reason}") from error

    if not isinstance(payload, dict):
        raise ValueError("Odpowiedź /rag/search nie jest obiektem JSON.")
    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("Odpowiedź /rag/search nie zawiera listy 'results'.")
    return results


def precision_at_k(
    retrieved_sources: Sequence[str], expected_sources: Sequence[str], k: int
) -> float:
    """Odsetek top-k źródeł, które są oznaczone jako oczekiwane."""
    if k <= 0:
        return 0.0
    top_sources = retrieved_sources[:k]
    hits = sum(
        any(source.startswith(prefix) for prefix in expected_sources)
        for source in top_sources
    )
    return hits / k


def recall_at_k(
    retrieved_sources: Sequence[str], expected_sources: Sequence[str], k: int
) -> float:
    """Odsetek oczekiwanych źródeł znalezionych w top-k."""
    if not expected_sources:
        return 0.0
    top_sources = retrieved_sources[:k]
    hits = sum(
        any(source.startswith(expected) for source in top_sources)
        for expected in expected_sources
    )
    return hits / len(expected_sources)


def unique_sources(results: Sequence[dict[str, Any]]) -> list[str]:
    """Zredukuj wiele fragmentów tej samej transkrypcji do jednego źródła."""
    seen: set[str] = set()
    sources = []
    for result in results:
        filename = result.get("filename")
        if isinstance(filename, str) and filename and filename not in seen:
            seen.add(filename)
            sources.append(filename)
    return sources


def evaluate_threshold(
    threshold: float,
    results_by_query: dict[str, list[dict[str, Any]]],
    top_k: int = 5,
) -> dict[str, float]:
    """Compute mean precision@k and recall@k after filtering scores."""
    precisions, recalls = [], []
    for item in GOLD_SET:
        results = results_by_query[item["query"]]
        filtered = [result for result in results if result["score"] >= threshold]
        sources = unique_sources(filtered)
        expected = item["expected_sources"]
        precisions.append(precision_at_k(sources, expected, top_k))
        recalls.append(recall_at_k(sources, expected, top_k))
    return {
        "threshold": threshold,
        "avg_precision": sum(precisions) / len(precisions),
        "avg_recall": sum(recalls) / len(recalls),
    }


def f1_score(precision, recall):
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate score thresholds against indexed ECB transcripts."
    )
    parser.add_argument(
        "--api",
        default="http://127.0.0.1:8000",
        help="Audio RAG API base URL (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of unique source files used for metrics (1-20; default: 5)",
    )
    args = parser.parse_args()
    if not 1 <= args.top_k <= SEARCH_LIMIT:
        parser.error(f"--top-k must be between 1 and {SEARCH_LIMIT}")

    results_by_query = {}
    try:
        for item in GOLD_SET:
            results_by_query[item["query"]] = retrieve(item["query"], args.api)
    except (RuntimeError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(
            f"Nie udało się pobrać wyników z API {args.api}: {error}. "
            "Uruchom API i sprawdź, czy ChromaDB jest dostępna."
        ) from error

    if not any(results_by_query.values()):
        raise SystemExit(
            "API zwróciło 0 wyników. Najpierw zaindeksuj transkrypcje audio w ChromaDB."
        )

    has_expected_source = any(
        any(
            result.get("filename", "").startswith(prefix)
            for prefix in item["expected_sources"]
        )
        for item in GOLD_SET
        for result in results_by_query[item["query"]]
    )
    if not has_expected_source:
        print(
            "Uwaga: żaden oczekiwany plik nie pojawił się w wynikach. "
            "Sprawdź, czy pliki z GOLD_SET są zaindeksowane.\n"
        )

    print(f"{'Próg':>6} | {'Precision':>10} | {'Recall':>8} | {'F1':>6}")
    print("-" * 40)

    results = []
    for threshold in THRESHOLDS:
        metrics = evaluate_threshold(threshold, results_by_query, top_k=args.top_k)
        f1 = f1_score(metrics["avg_precision"], metrics["avg_recall"])
        results.append({**metrics, "f1": f1})
        print(
            f"{threshold:>6.2f} | {metrics['avg_precision']:>10.2%} | "
            f"{metrics['avg_recall']:>8.2%} | {f1:>6.2%}"
        )

    best = max(results, key=lambda x: x["f1"])
    print(f"\nNajlepszy próg (max F1): {best['threshold']:.2f} "
          f"(precision={best['avg_precision']:.2%}, recall={best['avg_recall']:.2%})")


if __name__ == "__main__":
    main()

