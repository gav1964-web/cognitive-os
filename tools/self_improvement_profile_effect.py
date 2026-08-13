"""Run a same-source control/treatment profile effect trial."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.local_inference import LocalInferenceConfig
from runtime.self_improvement_profile_effect import evaluate_profile_effect, stage_profile_effect
from runtime.self_improvement_training import _evaluate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    project = Path(args.project_dir).resolve()
    config = LocalInferenceConfig(
        base_url="http://unused", model="deterministic-profile-effect",
        advisory_context={"preferred_source": args.source},
    )
    effect = evaluate_profile_effect(
        project, args.source,
        lambda: _evaluate(root, project, write=True, spec_writer_config=config),
    )
    candidate = stage_profile_effect(root, project, effect) if args.write else None
    effect["knowledge_candidate_path"] = candidate.as_posix() if candidate else None
    print(json.dumps(effect, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
