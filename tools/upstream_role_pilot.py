"""Evaluate Analyzer, Architect and SpecWriter on explicit development scenarios."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.stage_finalization_workspace import owned_path
from runtime.upstream_role_pilot import run_upstream_role_pilot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    parser.add_argument('--manifest', default='evaluation/upstream_roles/manifest.json')
    parser.add_argument('--references', default='evaluation/upstream_roles/reference_inputs.json')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    path = owned_path(root, args.output)
    if path.exists():
        parser.error('output already exists; preserve the previous attempt')
    result = run_upstream_role_pilot(root, manifest_path=args.manifest, references_path=args.references)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'summary': result['summary'], 'receipt': args.output}))
    return 0 if result['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
