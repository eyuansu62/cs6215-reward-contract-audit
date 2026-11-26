def score_answer(self, answer: Optional[str], entry: dict[str, Any]) -> float:
    oracle_answer = entry["answer"]
    reward = 0.0
    if answer is not None:
        oracle_answer_parsed = self._normalize_answer(oracle_answer)
        answer_parsed = self._normalize_answer(answer)
        if oracle_answer_parsed == answer_parsed:
            reward = 1.0
        elif math.prod(oracle_answer_parsed) == math.prod(answer_parsed):
            reward = 0.5
        else:
            reward = 0.01

    return reward
