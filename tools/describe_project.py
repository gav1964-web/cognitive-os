"""Describe a project using the registered competency and configured model route."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.project_description import describe_project, render_description, description_model_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-dir', required=True)
    parser.add_argument('--output', required=True, help='JSON receipt; readable Markdown is saved alongside')
    parser.add_argument('--language', default='ru')
    parser.add_argument('--owner-note', action='append', default=[])
    parser.add_argument('--review-context-profile', choices=['default', 'expanded'], default='default')
    parser.add_argument('--timeout', type=float, help='Per-request model timeout; defaults to configured profile')
    args = parser.parse_args()
    config = description_model_config()
    if args.timeout is not None:
        if args.timeout <= 0:
            parser.error('--timeout must be positive')
        config = replace(config, timeout_seconds=args.timeout)
    report = describe_project(Path(args.project_dir), language=args.language, owner_notes=args.owner_note,
                              config=config, review_context_profile=args.review_context_profile)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    output.with_suffix('.md').write_text(render_description(report), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'output': str(output),
                      'reason': report.get('reason'), 'telemetry': report['telemetry']}, ensure_ascii=False))
    return 0 if report['status'] == 'described' else 2


if __name__ == '__main__':
    raise SystemExit(main())
