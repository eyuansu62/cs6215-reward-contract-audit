def score(answer, entry):
    distance = abs(float(answer) - entry["value"])
    if not math.isfinite(distance):
        return 0.0
    return min(1.0, math.exp(-distance))

