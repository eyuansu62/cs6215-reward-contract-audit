def score(answer, entry):
    distance = float(answer)
    if not math.isfinite(entry["value"]):
        return 0.0
    return min(1.0, math.exp(-distance))

