"""Keep explicitly configured pytest temporary roots usable in a clean checkout."""
from pathlib import Path


def pytest_configure(config):
    # pytest creates/removes basetemp itself, but expects its parent to exist.
    # The repository default and canonical overrides use nested excluded paths.
    value = config.getoption('basetemp')
    if value:
        Path(value).resolve().parent.mkdir(parents=True, exist_ok=True)
