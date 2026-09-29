"""Run a pinned COS role checkpoint under the external support controller."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.remote_role_worker import main

if __name__ == '__main__':
    raise SystemExit(main())
