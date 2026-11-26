def score(answer, entry):
    if answer.strip().lower() != entry["answer"].strip().lower():
        return 0.0
    return float(bool(answer) == bool(entry["answer"]))

