def score_answer(self, answer: Optional[str], entry: dict, tol: float = 1e-4) -> float:
    """
        Compute reward for LLM answer against oracle probability.
        Handles decimals, fractions, small numeric errors, and extra text.
        """
    reward = 0.0
    oracle_answer = entry["answer"]

    if answer is None or len(answer.strip()) == 0:
        return reward

    answer = answer.replace(",", "")
    oracle_answer = oracle_answer.replace(",", "")

    try:
        answer_float = float(Fraction(answer))
        oracle_answer_float = float(Fraction(oracle_answer))
    except (ValueError, ZeroDivisionError):
        return reward

    if abs(answer_float - oracle_answer_float) <= tol:
        return 1.0

    answer_str = f"{answer_float:.10g}"
    oracle_answer_str = f"{oracle_answer_float:.10g}"

    # Partial Reward for matching prefix
    match_len = 0
    for a_char, o_char in zip(answer_str, oracle_answer_str):
        if a_char == o_char:
            match_len += 1
        else:
            break

    reward = match_len / min(len(oracle_answer_str), len(answer_str))

    return reward
