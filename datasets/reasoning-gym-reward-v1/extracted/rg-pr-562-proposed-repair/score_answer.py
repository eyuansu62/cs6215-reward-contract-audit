def score_answer(self, answer: Optional[str], entry: dict) -> float:
    """Score the answer using exponential distance-based scoring."""
    if answer is None:
        return 0.0

    try:
        student_result = self.parse_string_to_complex(answer)
        if student_result is None:
            return 0.0

        expected_result = complex(*entry["metadata"]["result"])
        distance = abs(student_result - expected_result)

        if not math.isfinite(distance):
            return 0.0

        return math.exp(-distance)

    except (ValueError, TypeError):
        return 0.0
