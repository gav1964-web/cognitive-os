import json
from pathlib import Path

def total(path):
    values = json.loads(Path(path).read_text())
    return sum(values)
