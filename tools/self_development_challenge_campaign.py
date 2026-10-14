"""Plan or execute the bounded prospective challenge campaign."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.self_development_challenge_campaign import (
    build_challenge_manifest,
    load_challenge_campaign_policy,
    run_challenge_campaign,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    policy = load_challenge_campaign_policy(str(root / "config" / "self_development_challenge_campaign.json"))
    manifest = build_challenge_manifest(root=root, policy=policy)
    report = (
        run_challenge_campaign(
            root=root,
            manifest=manifest,
            certification_receipt=str(policy["certification_receipt"]),
        )
        if args.execute else manifest
    )
    if args.write:
        directory = root / "artifacts" / "self_development"
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        kind = "challenge_campaign" if args.execute else "challenge_manifest"
        path = directory / f"self_development_{kind}_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.relative_to(root).as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if report["status"] in {"blocked", "local_corpus_shortage"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
