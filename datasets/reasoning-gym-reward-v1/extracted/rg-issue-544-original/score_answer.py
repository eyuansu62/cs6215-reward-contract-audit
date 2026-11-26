def score_answer(self, answer: Optional[str], entry: Dict[str, any]) -> float:
    """Determine if the solution provided solves the GoL task.

        The function awards 1.0 for a correct answer.

        Args:
            answer (Optional[str]): The user's answer.
            entry (Dict[str, any]): The original dataset entry containing the correct answer.

        Returns:
            float: The computed score between 0.0 and 1.0.
        """

    if answer is not None and bool(answer) == bool(entry["answer"]):
        # python's bool conversion is very tolerant and normally doesn't raise exceptions
        return 1.0
    return 0.0
