"""Build an offline, hashed Windows service bundle without installing anything.

The private stdlib/pywin32 runtime does not depend on the user's profile or venv.
No COS config, credentials, project corpus or external downloads are included.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'runtime/__init__.py', 'runtime/remote_support_protocol.py',
    'runtime/remote_support_windows.py', 'runtime/remote_support_exchange.py',
    'runtime/remote_support_release.py', 'runtime/remote_support_daemon.py',
    'runtime/remote_support_deployment.py', 'tools/remote_support_service.py',
    'tools/remote_support_install.py',
)


def build(destination):
    if os.name != 'nt' or sys.version_info[:2] < (3, 10):
        raise ValueError('support_bundle_requires_windows_python310_or_newer')
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    base = Path(sys.base_prefix)
    private = destination / 'python'
    private.mkdir()
    for pattern in ('python.exe', 'python*.dll', 'vcruntime*.dll', 'LICENSE.txt'):
        for source in base.glob(pattern):
            shutil.copy2(source, private / source.name)
    ignore = shutil.ignore_patterns('__pycache__', '*.pyc', 'site-packages', 'test', 'tests', 'idlelib', 'tkinter', 'turtledemo', 'ensurepip')
    shutil.copytree(base / 'Lib', private / 'Lib', ignore=ignore)
    shutil.copytree(base / 'DLLs', private / 'DLLs', ignore=ignore)
    import win32service
    import pywintypes
    win32 = Path(win32service.__file__).parent
    site = private / 'Lib/site-packages'
    site.mkdir()
    # Closed allowlist: do not copy the user's site-packages or executable .pth files.
    for name in ('win32api', 'win32service', 'servicemanager', 'win32event', 'win32security', 'win32job', '_win32sysloader'):
        shutil.copy2(win32 / (name + '.pyd'), site / (name + '.pyd'))
    for name in ('win32serviceutil', 'win32con', 'winerror', 'pywintypes'):
        shutil.copy2(win32 / 'lib' / (name + '.py'), site / (name + '.py'))
    shutil.copy2(pywintypes.__file__, private / Path(pywintypes.__file__).name)
    for source in win32.parent.glob('pywin32*.dist-info/*'):
        if source.is_file() and ('license' in source.name.lower() or source.name == 'METADATA'):
            target = destination / 'licenses' / source.name
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(source, target)
    for name in FILES:
        target = destination / 'app' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    probe = subprocess.run([str(private/'python.exe'), '-I', '-B', '-c',
        'import sys,ssl,hashlib,servicemanager,win32serviceutil,win32security,win32job; '
        'print(sys.prefix)'], capture_output=True, text=True, timeout=30)
    if probe.returncode or Path(probe.stdout.strip()).resolve() != private:
        raise ValueError('support_private_python_probe_failed:' + probe.stderr[-2000:])
    files = {p.relative_to(destination).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(destination.rglob('*')) if p.is_file()}
    manifest = {'schema':'cos.worker_bundle.v1', 'python':sys.version.split()[0], 'files':files}
    (destination/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return {'bundle':str(destination), 'files':len(files),
            'manifest_sha256':hashlib.sha256((destination/'manifest.json').read_bytes()).hexdigest(),
            'private_python_imports':'passed', 'installed':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))
