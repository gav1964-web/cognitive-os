"""Validate or install a prepared Windows worker bundle (installation needs admin)."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.remote_support_deployment import install, verify_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--controller-sid')
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    if args.install:
        if not args.controller_sid:
            parser.error('--install requires --controller-sid')
        result = install(args.bundle, args.controller_sid)
    else:
        manifest = verify_bundle(args.bundle)
        result = {'verified':True, 'files':len(manifest['files']), 'installed':False}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
