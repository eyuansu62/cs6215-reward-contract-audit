def score(answer, entry):
    return 1.0 if bool(answer) == bool(entry["answer"]) else 0.0

