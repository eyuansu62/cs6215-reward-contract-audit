def score(answer, entry):
    distance = float(answer)
    if math.isfinite(distance):
        return min(1.0, math.exp(-distance))
    return 0.0

