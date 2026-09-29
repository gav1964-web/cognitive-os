"""Fresh Windows file-exchange directories with separate controller/worker ACLs.

This protects the controller boundary, not the worker's entire host environment.
Never apply this helper to an existing project or user directory.
"""
import os
import csv
import re
import subprocess
from pathlib import Path


def current_sid():
    result = subprocess.run(['whoami.exe','/user','/fo','csv','/nh'],capture_output=True,
                            text=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise ValueError('support_windows_identity_unavailable')
    return sid(next(csv.reader(result.stdout.splitlines()))[-1])


def sid(value):
    if not isinstance(value, str) or not re.fullmatch(r'S-1-5-(?:\d+-)*\d+', value):
        raise ValueError('support_windows_sid_invalid')
    return value


def acl(path, controller, worker=None, *, modify=False):
    if os.name != 'nt':
        raise ValueError('support_windows_required')
    sid(controller)
    if worker:
        sid(worker)
        if worker == controller:
            raise ValueError('support_distinct_identities_required')
    args = ['icacls.exe', str(Path(path).resolve()), '/inheritance:r', '/grant:r',
            '*' + controller + ':(OI)(CI)F', '*S-1-5-18:(OI)(CI)F']
    if worker:
        args += ['*' + worker + ':(OI)(CI)' + ('M' if modify else 'RX')]
    result = subprocess.run(args, capture_output=True, timeout=15,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise ValueError('support_windows_acl_failed:' + str(result.returncode))


def fresh_directory(path, controller, worker=None, *, modify=False):
    path = Path(path).resolve()
    path.mkdir(exist_ok=False)
    acl(path, controller, worker, modify=modify)
    return path
