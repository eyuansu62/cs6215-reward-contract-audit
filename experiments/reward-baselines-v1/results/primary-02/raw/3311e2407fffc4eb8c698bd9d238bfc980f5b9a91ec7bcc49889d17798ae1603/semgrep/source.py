@staticmethod
def parse_string_to_complex(answer: str) -> complex:
    if answer is None:
        return None

    try:
        # Normalize the answer string by removing spaces and converting to lowercase
        answer = answer.replace(" ", "").lower()

        # remove brackets
        while len(answer) > 1 and answer[0] == "(" and answer[-1] == ")":
            answer = answer[1:-1]

        # Convert mathematical notation 'i' to Python's 'j' for complex numbers
        answer = answer.replace("i", "j")

        # Handle real numbers (no imaginary part)
        if "j" not in answer:
            return complex(float(answer))

        # Handle pure imaginary numbers
        if answer == "j":
            return complex(0, 1)
        if answer == "-j":
            return complex(0, -1)

        # Handle cases like "7j" or "-7j" (no real part)
        if (
            answer.endswith("j")
            and not any(c in answer[:-1] for c in "+-")
            or (answer.startswith("-") and not any(c in answer[1:-1] for c in "+-"))
        ):
            # Extract coefficient
            coef = answer[:-1]
            if coef == "":
                coef = "1"
            elif coef == "-":
                coef = "-1"
            return complex(0, float(coef))

        # Handle complex numbers with both parts
        # Make sure there's a + or - before j if it's not at the beginning
        if "j" in answer and not answer.endswith("j"):
            return None  # Invalid format like "3j+2"

        # Handle cases like "3+j" (implicit 1)
        if "+j" in answer:
            answer = answer.replace("+j", "+1j")
        if "-j" in answer:
            answer = answer.replace("-j", "-1j")

        # Parse the normalized string into a complex number
        return complex(answer)

    except (ValueError, TypeError):
        return None

def score_answer(self, answer: Optional[str], entry: dict) -> float:
    """Score the answer using exponential distance-based scoring."""
    if answer is None:
        return 0.0

    try:
        student_result = self.parse_string_to_complex(answer)
        if student_result is None:
            return 0.0

        expected_result = complex(*entry["metadata"]["result"])
        distance = abs(student_result - expected_result)

        if not math.isfinite(distance):
            return 0.0

        return math.exp(-distance)

    except (ValueError, TypeError):
        return 0.0
