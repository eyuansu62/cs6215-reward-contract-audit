def _normalize_answer(self, answer: str) -> list[int]:
    """Parse and sort factors from a string"""
    if not answer or answer.strip() == "":
        return []

    return sorted([int(factor.strip()) for factor in answer.split("×") if factor.strip() != ""])
