def _sort_nested_list(self, lst: list[list[str]]) -> list[list[str]]:
    """Sort a nested list of strings"""
    return sorted([sorted(sublist) for sublist in lst], key=lambda x: x[0] if x else "")
