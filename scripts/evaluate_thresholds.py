import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from retriever import retrieve  # zakłada, że retriever.py jest w tym samym katalogu

# GOLD SET: pytanie -> zbiór numerów artykułów, które SĄ poprawną odpowiedzią.
GOLD_SET = [
    {"query": "Kto powołuje premiera?", "expected_articles": ["154"]},
    {"query": "Ile trwa kadencja Sejmu?", "expected_articles": ["98"]},
    {"query": "Kto może być prezydentem Polski?", "expected_articles": ["127"]},
    {"query": "Kiedy można wprowadzić stan wyjątkowy?", "expected_articles": ["230", "231", "232"]},
    {"query": "Jakie prawa ma obywatel polski?", "expected_articles": ["30", "31", "32", "33"]},
    {"query": "Jak zmienić Konstytucję?", "expected_articles": ["235"]},
    {"query": "Co to jest Trybunał Stanu?", "expected_articles": ["198", "199"]},
]


def precision_at_k(retrieved_ids, expected_ids, k):
    """Jaka część z top-k zwróconych wyników jest faktycznie poprawna."""
    top_k_ids = retrieved_ids[:k]
    if not top_k_ids:
        return 0.0
    hits = sum(1 for rid in top_k_ids if rid in expected_ids)
    return hits / len(top_k_ids)


def recall_at_k(retrieved_ids, expected_ids, k):
    """Jaka część OCZEKIWANYCH artykułów faktycznie znalazła się w top-k."""
    if not expected_ids:
        return 0.0
    top_k_ids = retrieved_ids[:k]
    hits = sum(1 for eid in expected_ids if eid in top_k_ids)
    return hits / len(expected_ids)


def evaluate_threshold(threshold, top_k=5):
    """
    Dla danego progu odcięcia liczy średnie precision@k i recall@k
    po całym gold secie. Próg jest tu symulowany poprzez odfiltrowanie
    wyników z retrieve() po score, bo retrieve() ma hardkodowany próg
    0.08 w oryginalnym kodzie — w realnym eksperymencie warto tymczasowo
    sparametryzować retrieve(), żeby przyjmowała threshold jako argument.
    """
    precisions, recalls = [], []
    for item in GOLD_SET:
        results = retrieve(item["query"], top_k=top_k * 2)  # bierzemy więcej, żeby ręcznie przefiltrować
        filtered = [r for r in results if r["score"] >= threshold]
        retrieved_ids = [r["art_num"] for r in filtered]
        precisions.append(precision_at_k(retrieved_ids, item["expected_articles"], top_k))
        recalls.append(recall_at_k(retrieved_ids, item["expected_articles"], top_k))
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
    thresholds_to_test = [0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25]

    print(f"{'Próg':>6} | {'Precision':>10} | {'Recall':>8} | {'F1':>6}")
    print("-" * 40)

    results = []
    for t in thresholds_to_test:
        r = evaluate_threshold(t)
        f1 = f1_score(r["avg_precision"], r["avg_recall"])
        results.append({**r, "f1": f1})
        print(f"{t:>6.2f} | {r['avg_precision']:>10.2%} | {r['avg_recall']:>8.2%} | {f1:>6.2%}")

    best = max(results, key=lambda x: x["f1"])
    print(f"\nNajlepszy próg (max F1): {best['threshold']:.2f} "
          f"(precision={best['avg_precision']:.2%}, recall={best['avg_recall']:.2%})")


if __name__ == "__main__":
    main()
