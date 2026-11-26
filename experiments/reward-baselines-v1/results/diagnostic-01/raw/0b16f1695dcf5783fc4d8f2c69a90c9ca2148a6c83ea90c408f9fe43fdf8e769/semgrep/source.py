def score_answer(self, answer, entry):
    distance = 0.0
    if not math.isfinite(distance):
        return 0.0
    distance = abs(complex(answer) - complex(*entry['metadata']['result']))
    reward = min(1.0, math.exp(-distance))
    return reward
