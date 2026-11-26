def score_answer(self, answer: Optional[str], entry: dict[str, Any]) -> float:
        """Overwrite this method in derived classes if a single oracle answer is not available."""
        oracle_answer = entry["answer"]
        reward = 0.0
        if isinstance(answer, str) and len(answer) > 0:
            if answer == oracle_answer:
                reward = 1.0
            elif oracle_answer in answer:
                reward = len(oracle_answer) / len(answer)
        return reward