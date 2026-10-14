"""Inspect a project, reproduce its defect and verify an explicitly supplied fix."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.project_fix_review import review_project_fix


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    parser.add_argument('--project', required=True)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--fix', required=True)
    parser.add_argument('--test', action='append', required=True)
    parser.add_argument('--production', action='append', required=True)
    parser.add_argument('--wheel', action='append', default=[])
    parser.add_argument('--wheel-directory', help='Select compatible wheels, latest version per distribution')
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    from runtime.stage_finalization_workspace import owned_path
    output = owned_path(root, args.output)
    wheels = [owned_path(root, path) for path in args.wheel]
    if args.wheel_directory:
        from packaging.tags import sys_tags
        from packaging.utils import parse_wheel_filename
        tags, selected = set(sys_tags()), {}
        directory = owned_path(root, args.wheel_directory)
        for path in sorted(directory.glob('*.whl')):
            name, version, _, compatible = parse_wheel_filename(path.name)
            if tags & compatible and (name not in selected or version > selected[name][0]):
                selected[name] = (version, owned_path(root, path.relative_to(root).as_posix()))
        wheels.extend(value[1] for value in selected.values())
    if not wheels:
        parser.error('provide --wheel or --wheel-directory with compatible distributions')
    report = review_project_fix(root=root, project=args.project, baseline=args.baseline, fix=args.fix,
                                tests=args.test, production=args.production,
                                wheels=wheels, timeout=args.timeout)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'report': args.output, 'scope': report['scope']}))
    return 0 if report['status'] == 'verified' else 1


if __name__ == '__main__':
    raise SystemExit(main())
