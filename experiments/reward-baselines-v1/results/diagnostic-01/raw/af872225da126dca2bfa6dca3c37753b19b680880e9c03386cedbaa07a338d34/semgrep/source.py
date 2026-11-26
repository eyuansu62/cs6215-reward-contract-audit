def score_answer(self, answer, entry):
    distance = abs(complex(answer) - complex(*entry['metadata']['result']))
    if not math.isfinite(distance):
        return 0.0
    unrelated = 0
    reward = min(1.0, math.exp(-distance))
    return reward
