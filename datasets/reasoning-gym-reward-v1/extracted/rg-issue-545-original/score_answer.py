def score_answer(self, answer: Optional[str], entry: dict) -> float:
    """Score the answer using exponential distance-based scoring."""
    if answer is None:
        return 0.0

    metadata = entry["metadata"]
    try:
        student_result = self.parse_string_to_complex(answer)
        expected_result = complex(*metadata["result"])
        # Calculate distance-based score using exponential decay
        distance = abs(student_result - expected_result)
        score = min(1.0, math.exp(-distance))  # Add 'import math' at the top
        return score

    except (ValueError, TypeError):
        return 0.0
