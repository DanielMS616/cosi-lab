def retrieve_e5(question, excerpts, score_question, *, top_k=3):
    """Gibt die besten Suchabschnitte mit Quelle, Text und Score zurück."""
    scores = score_question(question)

    ranked = sorted(
        zip(excerpts, scores, strict=True),
        key=lambda pair: float(pair[1]),
        reverse=True,
    )

    return [
        {**excerpt, "score": float(score)}
        for excerpt, score in ranked[:top_k]
    ]