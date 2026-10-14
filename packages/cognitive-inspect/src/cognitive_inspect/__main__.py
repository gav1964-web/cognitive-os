"""Print read-only project tree facts as JSON using the public scanner contract."""
import argparse
import json
import sys

from . import scan_project_tree


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', help='Project directory within the current directory or its parent')
    parser.add_argument('--max-files', type=int, default=5000)
    parser.add_argument('--max-depth', type=int, default=8)
    args = parser.parse_args(argv)
    try:
        result = scan_project_tree({'path': args.path, 'max_files': args.max_files,
                                    'max_depth': args.max_depth})
    except (ValueError, OSError) as exc:
        print(f'cognitive-inspect: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
