"""Layer-oriented MVP acceptance report writer."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mvp_acceptance_checks import Check, json_or_empty, payload_summary


class AcceptanceReport:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.started_at = now()
        self.results: list[dict[str, Any]] = []

    def command(self, name: str, command: list[str], *, layers: list[str], check: Check) -> dict[str, Any]:
        proc = subprocess.run(command, cwd=self.root, capture_output=True, text=True)
        payload = json_or_empty(proc.stdout)
        passed, detail = check(
            {
                "returncode": proc.returncode,
                "payload": payload,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        )
        result = {
            "name": name,
            "layers": layers,
            "command": command,
            "status": "ok" if passed else "failed",
            "detail": detail,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-1200:],
            "stderr_tail": proc.stderr[-1200:],
        }
        if isinstance(payload, dict):
            result["payload_summary"] = payload_summary(payload)
        self.results.append(result)
        if not passed:
            final = self.finish()
            print(json.dumps(final, ensure_ascii=False, indent=2))
            raise SystemExit(1)
        return payload if isinstance(payload, dict) else {}

    def finish(self) -> dict[str, Any]:
        status = "ok" if all(item["status"] == "ok" for item in self.results) else "failed"
        finished_at = now()
        layer_summary: dict[str, dict[str, int]] = {}
        for result in self.results:
            for layer in result["layers"]:
                row = layer_summary.setdefault(layer, {"ok": 0, "failed": 0})
                row[result["status"]] += 1
        payload = {
            "status": status,
            "started_at": self.started_at,
            "finished_at": finished_at,
            "report_json": "",
            "report_markdown": "",
            "layer_summary": layer_summary,
            "results": self.results,
        }
        report_dir = self.root / "artifacts" / "acceptance"
        report_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        json_path = report_dir / f"mvp_acceptance_{stamp}.json"
        md_path = report_dir / f"mvp_acceptance_{stamp}.md"
        payload["report_json"] = json_path.as_posix()
        payload["report_markdown"] = md_path.as_posix()
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        md_path.write_text(markdown(payload), encoding="utf-8")
        return payload


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# MVP Acceptance Report",
        "",
        f"Status: `{payload['status']}`",
        f"Started: `{payload['started_at']}`",
        f"Finished: `{payload['finished_at']}`",
        "",
        "## Layers",
    ]
    for layer, row in sorted(payload["layer_summary"].items()):
        lines.append(f"- `{layer}`: ok={row['ok']}, failed={row['failed']}")
    lines.extend(["", "## Scenarios"])
    for result in payload["results"]:
        layers = ", ".join(result["layers"])
        lines.append(f"- `{result['status']}` `{result['name']}` ({layers}): {result['detail']}")
    lines.append("")
    return "\n".join(lines)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()
