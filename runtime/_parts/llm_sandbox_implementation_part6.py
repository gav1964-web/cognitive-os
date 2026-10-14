from __future__ import annotations

import json
import re
import shutil
import subprocess
import ast
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from runtime.interface_contracts import interface_contract_for_operation
from runtime.local_inference import LocalInferenceError, call_json_chat
from runtime.operation_recipe import recipe_from_operation, validate_operation_recipe
from runtime.operation_recipe_rules import load_operation_recipe_rules
from runtime.sandbox_operation_graph import build_sandbox_operation_graph
from runtime.sandbox_programmer_profiles import expression_policy, load_sandbox_programmer_profiles
from runtime.sandbox_release_policy import sandbox_implementation_policy

def _llm_policy(*, use_model: bool) -> dict[str, Any]:
    configured = dict(sandbox_implementation_policy().get("llm_policy") or {})
    return {
        "llm_as_hypothesis_source": bool(use_model),
        "llm_output_executed_directly": configured.get("llm_output_executed_directly", False),
        "allowlisted_contract_required": configured.get("allowlisted_contract_required", True),
        "sandbox_only": configured.get("sandbox_only", True),
    }
