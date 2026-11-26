def score(answer, entry):
    return float(bool(answer) == bool(entry["answer"]))

