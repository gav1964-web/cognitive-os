import json
import subprocess
from pathlib import Path


def legacy_process_all():
    raw = Path("input.txt").read_text(encoding="utf-8")
    rows = [line.split(",") for line in raw.splitlines()]
    cleaned = []
    for row in rows:
        if not row:
            continue
        subprocess.run(["echo", row[0]], check=False)
        cleaned.append({"name": row[0].strip(), "value": row[-1].strip()})
    if cleaned:
        Path("out.json").write_text(json.dumps(cleaned), encoding="utf-8")
    else:
        Path("errors.log").write_text("empty", encoding="utf-8")
    return cleaned
