def score(answer, entry):
    distance = abs(float(answer) - entry["value"])
    score = min(1.0, math.exp(-distance))
    return score

