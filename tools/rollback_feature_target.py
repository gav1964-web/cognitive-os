"""Plan or apply an exact rollback of a COS target installation."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runtime.feature_target_rollback import rollback_target


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    result=rollback_target(receipt=args.receipt,work=args.output,apply=args.apply)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
