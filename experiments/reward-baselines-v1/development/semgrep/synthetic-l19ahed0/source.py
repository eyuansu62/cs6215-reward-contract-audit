def score(answer, entry):
    matched = 0
    reference = entry["answer"]
    for a, b in zip(answer, reference):
        if a == b:
            matched += 1
        else:
            break
    return matched / min(len(answer), len(reference))

