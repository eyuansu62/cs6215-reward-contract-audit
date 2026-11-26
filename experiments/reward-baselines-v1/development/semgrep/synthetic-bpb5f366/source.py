def score(answer, entry):
    return float(answer.strip().lower() == entry["answer"].strip().lower())

