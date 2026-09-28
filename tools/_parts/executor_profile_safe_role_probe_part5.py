from __future__ import annotations

def _case_project(
    work_root: Path, row: dict[str, Any], *, target_file: str,
    cli_interface: str, web_interface: str, provider_interface: str,
    stateful_interface: str,
    async_interface: str,
    io_interface: str,
    framework_interface: str,
) -> Path:
    project = work_root / f"{row['project']}_{row['symbol']}"
    project.mkdir(parents=True, exist_ok=True)
    (project / target_file).write_text(str(row["source"]) + "\n", encoding="utf-8")
    input_block = {
        "argv_json": (
            "        if len(args) != 1:\n"
            "            raise ValueError('expected one JSON argument')\n"
            "        value = json.loads(args[0])\n"
        ),
        "stdin_json": (
            "        if args:\n"
            "            raise ValueError('arguments are not accepted')\n"
            "        value = json.loads(sys.stdin.read())\n"
        ),
        "file_json": (
            "        if len(args) != 1:\n"
            "            raise ValueError('expected one input path')\n"
            "        with open(args[0], encoding='utf-8') as stream:\n"
            "            value = json.load(stream)\n"
        ),
    }[cli_interface]
    (project / "cli.py").write_text(
        "import json\n"
        "import sys\n"
        f"from {Path(target_file).stem} import {row['symbol']}\n\n"
        "def main(argv=None):\n"
        "    args = list(sys.argv[1:] if argv is None else argv)\n"
        "    try:\n"
        + input_block
        + "    except (OSError, ValueError) as exc:\n"
        "        print(f'input error: {exc}', file=sys.stderr)\n"
        "        return 2\n"
        + f"    print(json.dumps({row['symbol']}(value), ensure_ascii=False, sort_keys=True))\n"
        "    return 0\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )
    (project / "web_app.py").write_text(
        _web_app_source(target_file=target_file, symbol=str(row["symbol"]), interface=web_interface),
        encoding="utf-8",
    )
    (project / "provider_adapter.py").write_text(
        _provider_adapter_source(
            target_file=target_file,
            symbol=str(row["symbol"]),
            interface=provider_interface,
        ),
        encoding="utf-8",
    )
    (project / "state_adapter.py").write_text(
        _state_adapter_source(
            target_file=target_file,
            symbol=str(row["symbol"]),
            interface=stateful_interface,
        ),
        encoding="utf-8",
    )
    (project / "async_adapter.py").write_text(
        _async_adapter_source(
            target_file=target_file,
            symbol=str(row["symbol"]),
            interface=async_interface,
        ),
        encoding="utf-8",
    )
    (project / "io_adapter.py").write_text(
        _io_adapter_source(
            target_file=target_file, symbol=str(row["symbol"]), interface=io_interface
        ),
        encoding="utf-8",
    )
    (project / "framework_adapter.py").write_text(
        _framework_adapter_source(
            target_file=target_file,
            symbol=str(row["symbol"]),
            interface=framework_interface,
        ),
        encoding="utf-8",
    )
    return project


def _cli_check(project_dir: Path, row: dict[str, Any], cli_interface: str) -> dict[str, Any]:
    profile = dict(contract_profile_for_operator(str(row["operator_id"])) or {})
    sample = profile.get("sample_input")
    expected = json.dumps(profile.get("expected_output"), ensure_ascii=False, sort_keys=True)
    payload = json.dumps(sample, ensure_ascii=False)
    command = [sys.executable, "cli.py"]
    stdin = None
    if cli_interface == "argv_json":
        command.append(payload)
    elif cli_interface == "stdin_json":
        stdin = payload
    else:
        input_path = project_dir / ".role_trial_input.json"
        input_path.write_text(payload, encoding="utf-8")
        command.append(input_path.name)
    completed = subprocess.run(
        command,
        cwd=project_dir,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    actual = completed.stdout.strip()
    invalid = subprocess.run(
        [sys.executable, "cli.py", "unexpected"] if cli_interface != "stdin_json" else [sys.executable, "cli.py", "unexpected"],
        cwd=project_dir,
        input=None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    passed = (
        completed.returncode == 0 and actual == expected and not completed.stderr.strip()
        and invalid.returncode == 2 and bool(invalid.stderr.strip())
        and "Traceback" not in invalid.stderr
    )
    return {
        "status": "passed" if passed else "failed",
        "returncode": completed.returncode,
        "expected_stdout": expected,
        "actual_stdout": actual,
        "stderr_tail": completed.stderr[-500:],
        "invalid_returncode": invalid.returncode,
        "invalid_stderr_tail": invalid.stderr[-500:],
    }

