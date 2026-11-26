def score(answer, entry):
    if answer == entry["answer"]:
        return 1.0
    return 0.05

