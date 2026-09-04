from __future__ import annotations

def _framework_check(
    project_dir: Path, row: dict[str, Any], framework_interface: str
) -> dict[str, Any]:
    profile = dict(contract_profile_for_operator(str(row["operator_id"])) or {})
    value = json.dumps(profile.get("sample_input"), ensure_ascii=False)
    expected = json.dumps(
        {"effects": 1, "result": profile.get("expected_output")},
        ensure_ascii=False,
        sort_keys=True,
    )
    completed = subprocess.run(
        [sys.executable, "framework_adapter.py", value], cwd=project_dir,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    invalid = subprocess.run(
        [sys.executable, "framework_adapter.py", value, "--invalid"], cwd=project_dir,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    actual = completed.stdout.strip()
    try:
        effect_count = int(dict(json.loads(actual)).get("effects") or 0)
    except (TypeError, ValueError, json.JSONDecodeError):
        effect_count = 0
    passed = (
        completed.returncode == 0 and actual == expected and not completed.stderr.strip()
        and invalid.returncode == 2 and bool(invalid.stderr.strip())
        and "Traceback" not in invalid.stderr
    )
    return {
        "status": "passed" if passed else "failed",
        "interface": framework_interface,
        "returncode": completed.returncode,
        "effect_count": effect_count,
        "expected_stdout": expected,
        "actual_stdout": actual,
        "stderr_tail": completed.stderr[-500:],
        "invalid_returncode": invalid.returncode,
        "invalid_stderr_tail": invalid.stderr[-500:],
    }


def _io_check(project_dir: Path, row: dict[str, Any], io_interface: str) -> dict[str, Any]:
    profile = dict(contract_profile_for_operator(str(row["operator_id"])) or {})
    value = json.dumps(profile.get("sample_input"), ensure_ascii=False)
    expected = json.dumps(
        {"operations": 1, "result": profile.get("expected_output")},
        ensure_ascii=False,
        sort_keys=True,
    )
    completed = subprocess.run(
        [sys.executable, "io_adapter.py", value], cwd=project_dir,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    invalid = subprocess.run(
        [sys.executable, "io_adapter.py", value, "--invalid"], cwd=project_dir,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    actual = completed.stdout.strip()
    try:
        operation_count = int(dict(json.loads(actual)).get("operations") or 0)
    except (TypeError, ValueError, json.JSONDecodeError):
        operation_count = 0
    passed = (
        completed.returncode == 0 and actual == expected and not completed.stderr.strip()
        and invalid.returncode == 2 and bool(invalid.stderr.strip())
        and "Traceback" not in invalid.stderr
    )
    return {
        "status": "passed" if passed else "failed",
        "interface": io_interface,
        "returncode": completed.returncode,
        "operation_count": operation_count,
        "expected_stdout": expected,
        "actual_stdout": actual,
        "stderr_tail": completed.stderr[-500:],
        "invalid_returncode": invalid.returncode,
        "invalid_stderr_tail": invalid.stderr[-500:],
    }


def _async_check(
    project_dir: Path, row: dict[str, Any], async_interface: str
) -> dict[str, Any]:
    profile = dict(contract_profile_for_operator(str(row["operator_id"])) or {})
    value = json.dumps(profile.get("sample_input"), ensure_ascii=False)
    expected = json.dumps(
        {"result": profile.get("expected_output"), "tasks": 1},
        ensure_ascii=False,
        sort_keys=True,
    )
    completed = subprocess.run(
        [sys.executable, "async_adapter.py", value], cwd=project_dir,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    timeout = subprocess.run(
        [sys.executable, "async_adapter.py", value, "--timeout"], cwd=project_dir,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    actual = completed.stdout.strip()
    try:
        task_count = int(dict(json.loads(actual)).get("tasks") or 0)
    except (TypeError, ValueError, json.JSONDecodeError):
        task_count = 0
    passed = (
        completed.returncode == 0 and actual == expected and not completed.stderr.strip()
        and timeout.returncode == 2 and bool(timeout.stderr.strip())
        and "Traceback" not in timeout.stderr
    )
    return {
        "status": "passed" if passed else "failed",
        "interface": async_interface,
        "returncode": completed.returncode,
        "task_count": task_count,
        "expected_stdout": expected,
        "actual_stdout": actual,
        "stderr_tail": completed.stderr[-500:],
        "timeout_returncode": timeout.returncode,
        "timeout_stderr_tail": timeout.stderr[-500:],
    }


def _stateful_check(
    project_dir: Path, row: dict[str, Any], stateful_interface: str
) -> dict[str, Any]:
    profile = dict(contract_profile_for_operator(str(row["operator_id"])) or {})
    value = json.dumps(profile.get("sample_input"), ensure_ascii=False)
    expected = json.dumps(
        {"result": profile.get("expected_output"), "row_count": 1},
        ensure_ascii=False,
        sort_keys=True,
    )
    completed = subprocess.run(
        [sys.executable, "state_adapter.py", value], cwd=project_dir,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    invalid = subprocess.run(
        [sys.executable, "state_adapter.py", value, "--invalid"], cwd=project_dir,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    actual = completed.stdout.strip()
    try:
        row_count = int(dict(json.loads(actual)).get("row_count") or 0)
        invalid_row_count = int(dict(json.loads(invalid.stdout)).get("row_count") or 0)
    except (TypeError, ValueError, json.JSONDecodeError):
        row_count = invalid_row_count = -1
    passed = (
        completed.returncode == 0 and actual == expected and not completed.stderr.strip()
        and invalid.returncode == 2 and invalid_row_count == 0
        and "Traceback" not in invalid.stderr
    )
    return {
        "status": "passed" if passed else "failed",
        "interface": stateful_interface,
        "returncode": completed.returncode,
        "row_count": row_count,
        "expected_stdout": expected,
        "actual_stdout": actual,
        "stderr_tail": completed.stderr[-500:],
        "invalid_returncode": invalid.returncode,
        "invalid_row_count": invalid_row_count,
        "invalid_stdout": invalid.stdout.strip(),
        "invalid_stderr_tail": invalid.stderr[-500:],
    }


def _provider_check(
    project_dir: Path, row: dict[str, Any], provider_interface: str
) -> dict[str, Any]:
    profile = dict(contract_profile_for_operator(str(row["operator_id"])) or {})
    sample = profile.get("sample_input")
    expected_payload = {"calls": 1, "result": profile.get("expected_output")}
    expected = json.dumps(expected_payload, ensure_ascii=False, sort_keys=True)
    value = json.dumps(sample, ensure_ascii=False)
    completed = subprocess.run(
        [sys.executable, "provider_adapter.py", value],
        cwd=project_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    invalid = subprocess.run(
        [sys.executable, "provider_adapter.py", value, "--invalid"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    actual = completed.stdout.strip()
    try:
        call_count = int(dict(json.loads(actual)).get("calls") or 0)
    except (TypeError, ValueError, json.JSONDecodeError):
        call_count = 0
    passed = (
        completed.returncode == 0
        and actual == expected
        and not completed.stderr.strip()
        and invalid.returncode == 2
        and bool(invalid.stderr.strip())
        and "Traceback" not in invalid.stderr
    )
    return {
        "status": "passed" if passed else "failed",
        "interface": provider_interface,
        "returncode": completed.returncode,
        "call_count": call_count,
        "expected_stdout": expected,
        "actual_stdout": actual,
        "stderr_tail": completed.stderr[-500:],
        "invalid_returncode": invalid.returncode,
        "invalid_stderr_tail": invalid.stderr[-500:],
    }


def _web_check(project_dir: Path, row: dict[str, Any], web_interface: str) -> dict[str, Any]:
    profile = dict(contract_profile_for_operator(str(row["operator_id"])) or {})
    sample = profile.get("sample_input")
    expected = json.dumps(profile.get("expected_output"), ensure_ascii=False, sort_keys=True)
    positive = _http_exchange(project_dir, web_interface, sample=sample, invalid=False)
    invalid = _http_exchange(project_dir, web_interface, sample=sample, invalid=True)
    passed = (
        positive["status_code"] == 200
        and positive["body"] == expected
        and invalid["status_code"] == 400
        and "Traceback" not in invalid["body"]
    )
    return {
        "status": "passed" if passed else "failed",
        "status_code": positive["status_code"],
        "expected_body": expected,
        "actual_body": positive["body"],
        "invalid_status_code": invalid["status_code"],
        "invalid_body": invalid["body"],
        "server_stderr_tail": positive["server_stderr_tail"],
    }


def _http_exchange(
    project_dir: Path, interface: str, *, sample: Any, invalid: bool
) -> dict[str, Any]:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = int(reservation.getsockname()[1])
    process = subprocess.Popen(
        [sys.executable, "web_app.py", str(port)],
        cwd=project_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    payload = json.dumps(sample, ensure_ascii=False)
    if interface == "post_json":
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/transform",
            data=(b"{" if invalid else payload.encode("utf-8")),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    elif interface == "get_query":
        query = "" if invalid else "?" + urllib.parse.urlencode({"input": payload})
        request = urllib.request.Request(f"http://127.0.0.1:{port}/transform{query}")
    else:
        headers = {} if invalid else {"X-Input": payload}
        request = urllib.request.Request(f"http://127.0.0.1:{port}/transform", headers=headers)
    status_code, body = 0, ""
    try:
        for attempt in range(40):
            try:
                with urllib.request.urlopen(request, timeout=2) as response:
                    status_code = int(response.status)
                    body = response.read().decode("utf-8")
                break
            except urllib.error.HTTPError as exc:
                status_code = int(exc.code)
                body = exc.read().decode("utf-8")
                break
            except urllib.error.URLError:
                if attempt == 39:
                    raise
                time.sleep(0.05)
        _, stderr = process.communicate(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            _, stderr = process.communicate(timeout=5)
    return {"status_code": status_code, "body": body, "server_stderr_tail": str(stderr)[-500:]}

