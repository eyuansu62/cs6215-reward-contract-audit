def score_answer(self, answer: Optional[str], entry: dict[str, Any]) -> float:
    """Determine if the solution provided is a valid palindrome.
        The answer is expected to be a single string

        Expected behavior:
        - Correct answer (palindrome with only correct letters in the correct quantities) gives 1.0
        - An answer that is a palindrome, but not with the same letters as provided, gives 0.05
        - An answer that is a string, but not a palindrome gives 0.02
        - An empty string gives 0.0
        - None gives 0.0.
        """
    if answer is None or not isinstance(answer, str):
        return 0.0  # No answer given

    if answer == "":
        return 0.0

    metadata = entry["metadata"]
    answer = answer.strip().lower()
    expected_letters = metadata["letters"]

    # Check if the answer is a palindrome
    if answer != answer[::-1]:
        return 0.02

    # Check if answer contains the same letters as provided (ignoring order)
    if sorted(answer) != sorted(expected_letters):
        return 0.05

    return 1.0  # Correct solution
