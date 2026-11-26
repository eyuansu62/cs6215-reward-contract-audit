def score_answer(self, answer, entry):
    distance = abs(complex(answer) - complex(*entry['metadata']['result']))
    if math.isfinite(distance):
        return min(1.0, math.exp(-distance))
    return 1.0
