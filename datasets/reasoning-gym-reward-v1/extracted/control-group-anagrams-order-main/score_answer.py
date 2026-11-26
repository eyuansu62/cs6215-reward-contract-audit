def score_answer(self, answer: Optional[str], entry: dict[str, Any]) -> float:
    """Score a single Group Anagrams question"""
    reward = 0.0
    if answer is not None:
        try:
            answer = json.loads(answer)
            oracle = entry["metadata"]["solution"]
            answer_str = json.dumps(self._sort_nested_list(answer))
            oracle_str = json.dumps(self._sort_nested_list(oracle))
            if answer_str == oracle_str:
                reward = 1.0
            else:
                reward = 0.01  # json parsable
        except Exception:
            reward = 0.0
    return reward
