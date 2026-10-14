"""Poll a controller-owned local exchange under the separately provisioned worker account."""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.remote_support_exchange import work_once


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exchange',required=True)
    parser.add_argument('--seconds',type=int,default=30)
    parser.add_argument('--worker-sid',required=True)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 3600:
        raise ValueError('support_worker_bounded_lifetime')
    from runtime.remote_support_windows import current_sid
    if current_sid() != args.worker_sid:
        raise ValueError('support_worker_identity_mismatch')
    until = time.monotonic()+args.seconds
    while time.monotonic()<until:
        rows = work_once(args.exchange)
        if rows:
            print(json.dumps(rows),flush=True)
        time.sleep(0.2)


if __name__ == '__main__':
    main()
