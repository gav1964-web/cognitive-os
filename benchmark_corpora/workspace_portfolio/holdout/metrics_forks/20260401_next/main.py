def metric_key(value: str) -> str:
    return value.strip().replace(" ", "_").lower()
