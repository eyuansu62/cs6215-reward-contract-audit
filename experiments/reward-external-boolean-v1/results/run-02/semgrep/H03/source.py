def prefix_exact_match(gold: str, pred: str) -> float:
    """
    The `prefix_exact_match` metric is particularly useful in the zero-shot setting, where the model is
    not given examples of the expected outputs and tends to output more tokens than it should.

    For example, for this zero-shot prompt from BoolQ,

    Passage: Elmendorf Air Force Base (IATA: EDF, ICAO: PAED, FAA LID: EDF) is a United States military facility
    in Anchorage, the largest city in Alaska. Originally known as Elmendorf Field, it became Elmendorf Air Force
    Base after World War II, and in 2010 it merged with nearby Fort Richardson to form Joint Base Elmendorf-Richardson.
    Question: Is there an air force base in anchorage alaska?
    Answer:

    the model could output up to `max_tokens` number of tokens "Yes, Elmendorf" instead of just "Yes".
    """
    if not pred:
        return 0

    return 1 if pred.strip().startswith(gold.strip()) else 0
