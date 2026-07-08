import json
from pathlib import Path


def load_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def write_json(path: str, value: str) -> None:
    Path(path).write_text(json.dumps({"text": value}), encoding="utf-8")


def main() -> None:
    raw = load_text("input.txt")
    normalized = normalize_text(raw)
    write_json("output.json", normalized)


if __name__ == "__main__":
    main()
