def normalize_query(query: str) -> str:
    return " ".join(query.lower().strip().split())
