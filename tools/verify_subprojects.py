"""Build sdist/wheel, install each package in a fresh venv and test without COS imports."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from xml.etree import ElementTree

PACKAGES = ("cognitive-inspect", "cognitive-replay")


def run(command: list[str], cwd: Path, env: dict, log: Path, timeout: int = 300) -> None:
    completed = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=timeout)
    log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(f"command exited {completed.returncode}; see {log}")


def copy_package(source: Path, target: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part in {"build", "dist", "__pycache__", ".pytest_cache"}
               or part.endswith(".egg-info") for part in relative.parts):
            continue
        if path.is_file():
            if not path.resolve().is_relative_to(source.resolve()):
                raise ValueError(f"package source escapes root: {path}")
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            hashes[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def verify(root: Path, name: str, work: Path, receipts: Path, env: dict, wheelhouse: Path | None) -> dict:
    started = time.monotonic()
    directory = work / name.removeprefix("cognitive-")
    directory.mkdir()
    logs = receipts / name
    logs.mkdir()
    row = {"package": name, "status": "failed", "source_sha256": {}, "logs": logs.relative_to(root).as_posix()}
    try:
        source = root / "packages" / name
        exported = directory / "source"
        row["source_sha256"] = copy_package(source, exported)
        dist = directory / "dist"
        run([sys.executable, "-I", "-m", "build", "--no-isolation", "--outdir", str(dist), str(exported)],
            directory, env, logs / "build.log")
        wheels, sdists = list(dist.glob("*.whl")), list(dist.glob("*.tar.gz"))
        if len(wheels) != 1 or len(sdists) != 1:
            raise ValueError("expected one wheel rebuilt from one sdist")
        row["distributions"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [*wheels, *sdists]}
        venv = directory / "venv"
        run([sys.executable, "-I", "-m", "venv", str(venv)], directory, env, logs / "venv.log")
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        install = [str(python), "-I", "-m", "pip", "--isolated", "install", "--disable-pip-version-check"]
        if wheelhouse:
            install.extend(["--no-index", "--find-links", str(wheelhouse)])
        else:
            install.extend(["--index-url", "https://pypi.org/simple", "--timeout", "30", "--retries", "1"])
        run([*install, str(wheels[0]) + "[test]"], directory, env, logs / "install.log")
        run([str(python), "-I", "-m", "pip", "check"], directory, env, logs / "dependencies.log")
        isolated = directory / "consumer"
        isolated.mkdir()
        shutil.copytree(exported / "tests", isolated / "tests")
        (isolated / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        arguments = ["tests", "-q", "--import-mode=importlib", "-p", "no:cacheprovider",
                     "--basetemp", str(directory / "tmp"), "--junitxml", str(logs / "result.xml")]
        package_root = name.replace("-", "_")
        script = (
            "import json,pathlib,sys; import pytest; "
            f"result=pytest.main({arguments!r}); "
            "loaded={n:str(pathlib.Path(m.__file__).resolve()) for n,m in sys.modules.items() "
            f"if n.split('.')[0] in {{{package_root!r},'runtime','plugins','tools'}} and getattr(m,'__file__',None)}}; "
            f"venv=pathlib.Path({str(venv)!r}).resolve(); "
            f"leaks={{n:p for n,p in loaded.items() if n.split('.')[0]!={package_root!r} or not pathlib.Path(p).is_relative_to(venv)}}; "
            f"pathlib.Path({str(logs / 'imports.json')!r}).write_text(json.dumps({{'loaded':loaded,'leaks':leaks}},indent=2),encoding='utf-8'); "
            "raise SystemExit(3 if leaks or not loaded else result)"
        )
        run([str(python), "-I", "-B", "-c", script], isolated, env, logs / "tests.log", timeout=600)
        suites = list(ElementTree.parse(logs / "result.xml").getroot())
        row["counts"] = {key: sum(int(s.get(key, "0")) for s in suites) for key in ("tests", "errors", "failures", "skipped")}
        row["import_audit"] = json.loads((logs / "imports.json").read_text(encoding="utf-8"))
        row["changed_sources"] = [p for p, digest in row["source_sha256"].items()
                                  if hashlib.sha256((source / p).read_bytes()).hexdigest() != digest]
        if row["changed_sources"]:
            raise ValueError("package sources changed during verification")
        row["status"] = "passed"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        row["error"] = str(exc)
    row["seconds"] = round(time.monotonic() - started, 2)
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--package", choices=PACKAGES, action="append")
    parser.add_argument("--wheelhouse", help="Optional complete offline dependency wheelhouse")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    identity = uuid.uuid4().hex[:8]
    work = root / ".nft" / f"pk-{identity}"
    work.mkdir(parents=True)
    receipts = root / "artifacts" / "verification" / "subprojects" / identity
    receipts.mkdir(parents=True)
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith(("PYTHON", "PYTEST", "PIP_", "COV_CORE")) and key.upper() != "VIRTUAL_ENV"}
    env.update({"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"})
    wheelhouse = Path(args.wheelhouse).resolve() if args.wheelhouse else None
    rows = []
    for name in dict.fromkeys(args.package or PACKAGES):
        row = verify(root, name, work, receipts, env, wheelhouse)
        rows.append(row)
        print(json.dumps({key: row[key] for key in ("package", "status", "seconds", "counts", "error") if key in row}), flush=True)
    report = {"kind": "installed_distribution_verification", "python": sys.version,
              "work": work.relative_to(root).as_posix(), "runs": rows}
    encoded = json.dumps(report, indent=2) + "\n"
    (receipts / "report.json").write_text(encoded, encoding="utf-8")
    (receipts.parent / "latest.json").write_text(encoded, encoding="utf-8")
    print(f"Receipt: {receipts / 'report.json'}", flush=True)
    return int(any(row["status"] != "passed" for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
