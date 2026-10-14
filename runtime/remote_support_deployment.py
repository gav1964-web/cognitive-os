"""Fresh Windows service deployment: reviewed files, protected root, virtual SID.

This installer is intentionally not an updater. Existing roots/services require
operator review. It never opens COS credentials or modifies existing projects.
"""
import ctypes
import hashlib
import json
import os
import shutil
import struct
import subprocess
from pathlib import Path

from .remote_support_windows import sid

SERVICE = 'CognitiveOSWorker'


def service_sid():
    words = struct.unpack('<5I', hashlib.sha1(SERVICE.upper().encode('utf-16le')).digest())
    return 'S-1-5-80-' + '-'.join(map(str, words))


def verify_bundle(bundle):
    bundle = Path(bundle).resolve()
    manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 'cos.worker_bundle.v1' or not manifest.get('files'):
        raise ValueError('support_bundle_manifest')
    expected = manifest['files']
    for name, wanted in expected.items():
        parts = name.split('/')
        if (not name or any(p in ('', '.', '..') for p in parts)
                or '\\' in name or ':' in name):
            raise ValueError('support_bundle_path')
        path = bundle.joinpath(*parts)
        for part in (path, *path.parents):
            if part == bundle:
                break
            if part.is_symlink() or (os.name == 'nt' and part.stat().st_file_attributes & 0x400):
                raise ValueError('support_bundle_link')
        if hashlib.sha256(path.read_bytes()).hexdigest() != wanted:
            raise ValueError('support_bundle_hash:' + name)
    actual = {p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file()}
    if actual != set(expected) | {'manifest.json'}:
        raise ValueError('support_bundle_extra_files')
    return manifest


def protect(path, controller, worker, *, writable=False):
    import win32security as security
    acl = security.ACL()
    for account, rights in [('S-1-5-18', 0x1F01FF), ('S-1-5-32-544', 0x1F01FF),
                            (controller, 0x1F01FF), (worker, 0x1301BF if writable else 0x1200A9)]:
        acl.AddAccessAllowedAceEx(security.ACL_REVISION, 3, rights,
                                 security.ConvertStringSidToSid(account))
    security.SetNamedSecurityInfo(str(path), security.SE_FILE_OBJECT,
        security.DACL_SECURITY_INFORMATION | security.PROTECTED_DACL_SECURITY_INFORMATION,
        None, None, acl, None)


def check_ancestors(destination, worker):
    import win32security as security
    # Virtual service identity is a member of these broad local groups.
    broad = {'S-1-1-0', 'S-1-5-11', 'S-1-5-32-545', 'S-1-5-6', 'S-1-5-80-0', worker}
    for parent in destination.parents:
        if parent.stat().st_file_attributes & 0x400:
            raise ValueError('support_deployment_reparse_ancestor')
        descriptor = security.GetNamedSecurityInfo(str(parent), security.SE_FILE_OBJECT,
                                                   security.DACL_SECURITY_INFORMATION)
        acl = descriptor.GetSecurityDescriptorDacl()
        if acl is None:
            raise ValueError('support_deployment_unprotected_ancestor')
        for index in range(acl.GetAceCount()):
            header, mask, account = acl.GetAce(index)
            if (header[0] == security.ACCESS_ALLOWED_ACE_TYPE and not header[1] & 8
                    and security.ConvertSidToStringSid(account) in broad
                    and mask & (0x40 | 0x10000 | 0x40000 | 0x80000 | 0x10000000)):
                raise ValueError('support_deployment_replaceable_ancestor:' + str(parent))


def install(bundle, controller):
    if os.name != 'nt' or not ctypes.windll.shell32.IsUserAnAdmin():
        raise PermissionError('support_install_requires_windows_administrator')
    sid(controller)
    import win32security
    account = win32security.LookupAccountSid(None, win32security.ConvertStringSidToSid(controller))
    if account[2] != win32security.SidTypeUser:
        raise ValueError('support_controller_must_be_user')
    worker = service_sid()
    if controller in {worker, 'S-1-1-0', 'S-1-5-11', 'S-1-5-32-545', 'S-1-5-80-0'}:
        raise ValueError('support_controller_must_be_dedicated_identity')
    bundle = Path(bundle).resolve()
    manifest = verify_bundle(bundle)
    program_data = ctypes.create_unicode_buffer(32768)
    if ctypes.windll.shell32.SHGetFolderPathW(None, 35, None, 0, program_data):
        raise ValueError('support_programdata_unavailable')
    destination = Path(program_data.value) / SERVICE
    if destination.exists():
        raise FileExistsError('support_deployment_already_exists:' + str(destination))
    check_ancestors(destination, worker)
    import win32service as services
    manager = services.OpenSCManager(None, None, services.SC_MANAGER_ALL_ACCESS)
    try:
        try:
            existing = services.OpenService(manager, SERVICE, services.SERVICE_QUERY_STATUS)
        except services.error as exc:
            if exc.winerror != 1060:
                raise
        else:
            services.CloseServiceHandle(existing)
            raise FileExistsError('support_service_already_exists')
        destination.mkdir(exist_ok=False)
        protect(destination, controller, worker)
        for name in manifest['files']:
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bundle / name, target)
        shutil.copyfile(bundle / 'manifest.json', destination / 'manifest.json')
        if verify_bundle(destination) != manifest:
            raise ValueError('support_bundle_changed_during_copy')
        for name in ('exchange', 'state'):
            (destination / name).mkdir()
            protect(destination / name, controller, worker, writable=name == 'state')
        config = {'schema':'cos.worker_service.v1', 'controller_sid':controller,
                  'worker_sid':worker, 'exchange':str(destination/'exchange'),
                  'state':str(destination/'state'), 'poll_seconds':0.5}
        (destination/'worker.json').write_text(json.dumps(config, indent=2)+'\n', encoding='utf-8')
        command = subprocess.list2cmdline([str(destination/'python/python.exe'), '-I', '-B',
            str(destination/'app/tools/remote_support_service.py'), str(destination/'worker.json')])
        handle = services.CreateService(manager, SERVICE, 'Cognitive OS file worker',
            services.SERVICE_ALL_ACCESS, services.SERVICE_WIN32_OWN_PROCESS,
            services.SERVICE_DEMAND_START, services.SERVICE_ERROR_NORMAL, command,
            None, 0, None, 'NT SERVICE\\' + SERVICE, None)
        try:
            services.ChangeServiceConfig2(handle, services.SERVICE_CONFIG_SERVICE_SID_INFO,
                                          services.SERVICE_SID_TYPE_UNRESTRICTED)
            services.StartService(handle, None)
            # Promote to auto-start only after a real identity-bound heartbeat.
            import time
            until = time.monotonic() + 30
            while time.monotonic() < until:
                status_file = destination/'state/status.json'
                if status_file.is_file():
                    status = json.loads(status_file.read_text(encoding='utf-8'))
                    if status.get('phase') == 'running' and status.get('worker_sid') == worker:
                        break
                if services.QueryServiceStatus(handle)[1] == services.SERVICE_STOPPED:
                    raise RuntimeError('support_service_stopped_during_startup')
                time.sleep(0.2)
            else:
                raise RuntimeError('support_service_readiness_timeout')
            services.ChangeServiceConfig(handle, services.SERVICE_NO_CHANGE,
                services.SERVICE_AUTO_START, services.SERVICE_NO_CHANGE, None, None, 0, None, None, None, None)
            services.ChangeServiceConfig2(handle, services.SERVICE_CONFIG_DELAYED_AUTO_START_INFO, True)
            services.ChangeServiceConfig2(handle, services.SERVICE_CONFIG_FAILURE_ACTIONS,
                {'ResetPeriod':86400, 'RebootMsg':'', 'Command':'',
                 'Actions':[(services.SC_ACTION_RESTART, 30000), (services.SC_ACTION_NONE, 0)]})
            services.ChangeServiceConfig2(handle, services.SERVICE_CONFIG_FAILURE_ACTIONS_FLAG, True)
        except Exception:
            try:
                services.ControlService(handle, services.SERVICE_CONTROL_STOP)
            except services.error:
                pass
            # Leave the failed deployment for inspection, never silently overwrite it.
            raise
        finally:
            services.CloseServiceHandle(handle)
    finally:
        services.CloseServiceHandle(manager)
    return {'installed':True, 'root':str(destination), 'worker_sid':worker,
            'execution':{'kind':'windows_file_worker.v1', 'root':str(destination/'exchange'),
                         'controller_sid':controller, 'worker_sid':worker}}
