def score_answer(self, answer, entry):
    if answer is not None and bool(answer) == bool(entry['answer']):
        if answer.strip().lower() == entry['answer'].strip().lower():
            return 1.0
    return 0.0
