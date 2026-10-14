import json
from pathlib import Path

from runtime.self_improving_foundation_trial import (
    _promotion_count,
    _prior_attempted_projects,
    _write_checkpoint,
    run_self_improving_foundation_trial,
)




def _report(cases, status="needs_work"):
    return {"status": status, "cases": cases}

























__all__ = [name for name in globals() if not name.startswith("__")]
