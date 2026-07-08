import csv
import json
from pathlib import Path


def load_csv(path: str) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def normalize_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{key: value.strip().lower() for key, value in row.items()} for row in rows]


def write_json(path: str, rows: list[dict[str, str]]) -> None:
    Path(path).write_text(json.dumps(rows), encoding="utf-8")


def run_pipeline() -> None:
    rows = load_csv("input.csv")
    normalized = normalize_rows(rows)
    write_json("output.json", normalized)
