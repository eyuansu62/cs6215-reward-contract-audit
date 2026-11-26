def score(answer, entry):
    if not math.isfinite(entry["getter"]()):
        return 0.0
    return min(1.0, math.exp(-entry["getter"]()))

