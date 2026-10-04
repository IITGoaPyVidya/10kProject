"""Local FinBERT sentiment engine (optional dependency: torch + transformers)."""
import threading
from functools import lru_cache

from app.core.config import Settings
from app.services.pdf import split_sentences

_infer_lock = threading.Lock()  # torch pipelines are not safe to share across threads


class LocalModelUnavailable(RuntimeError):
    """torch/transformers are not installed or the model failed to load."""


@lru_cache(maxsize=1)
def _load_pipeline(model_name: str):
    try:
        from transformers import pipeline

        return pipeline("text-classification", model=model_name, top_k=None,
                        truncation=True, max_length=512)
    except Exception as exc:
        raise LocalModelUnavailable(f"FinBERT unavailable: {exc}") from exc


def run_local_finbert(text: str, settings: Settings) -> dict:
    """Score each sentence; return summary, drift series, aggressive questions and extreme sentences."""
    sentences = split_sentences(text)[: settings.max_sentences]
    if not sentences:
        return {"summary": {"sentences": 0, "avg_score": 0.0, "extreme_count": 0},
                "drift": [], "questions": [], "extremes": []}

    clf = _load_pipeline(settings.finbert_model)
    with _infer_lock:
        outputs = clf(sentences, batch_size=16)

    rows = []
    for i, (sent, out) in enumerate(zip(sentences, outputs)):
        p = {d["label"].lower(): d["score"] for d in out}
        pos, neg, neu = p.get("positive", 0.0), p.get("negative", 0.0), p.get("neutral", 0.0)
        label = max((("positive", pos), ("negative", neg), ("neutral", neu)), key=lambda x: x[1])[0]
        rows.append({"idx": i, "sentence": sent, "positive": pos, "negative": neg,
                     "score": pos - neg, "label": label,
                     "strength": max(pos, neg)})

    thr = settings.extreme_threshold
    extremes = [r for r in rows if r["strength"] >= thr and r["label"] != "neutral"]

    # Sentiment drift: average over up to 20 equal slices of the document.
    bins = min(20, len(rows))
    buckets: list[list[dict]] = [[] for _ in range(bins)]
    for r in rows:
        buckets[r["idx"] * bins // len(rows)].append(r)
    drift = [{"segment": b + 1,
              "score": sum(r["score"] for r in rs) / len(rs),
              "positive": sum(r["positive"] for r in rs) / len(rs),
              "negative": sum(r["negative"] for r in rs) / len(rs)}
             for b, rs in enumerate(buckets) if rs]

    # Aggressive questions: most negative question sentences + the next 3 sentences as the response.
    questions = []
    for r in sorted((r for r in rows if r["sentence"].rstrip().endswith("?")),
                    key=lambda r: r["negative"], reverse=True)[:15]:
        resp = " ".join(x["sentence"] for x in rows[r["idx"] + 1: r["idx"] + 4])[:500]
        questions.append({"question": r["sentence"], "negative": round(r["negative"], 3), "response": resp})

    return {
        "summary": {"sentences": len(rows),
                    "avg_score": round(sum(r["score"] for r in rows) / len(rows), 4),
                    "extreme_count": len(extremes)},
        "drift": drift,
        "questions": questions,
        "extremes": [{"label": r["label"], "strength": round(r["strength"], 3), "sentence": r["sentence"]}
                     for r in sorted(extremes, key=lambda r: r["strength"], reverse=True)[:30]],
    }
