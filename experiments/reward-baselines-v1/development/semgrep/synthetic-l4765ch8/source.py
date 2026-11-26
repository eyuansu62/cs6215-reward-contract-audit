def score(answer, entry):
    distance = float(answer)
    if not math.isfinite(distance):
        return 0.0
    distance = entry["other"]
    return min(1.0, math.exp(-distance))

