"""Windows SCM host. Run from a protected deployment, not a writable project tree."""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def contain_process_tree():
    """Keep a noninherited job handle until process exit, including forced death.

    SCM recovery may restart the host, but its old children must not survive it.
    Failure to assign the job aborts startup before accepting any ticket.
    """
    import win32api
    import win32job
    job = win32job.CreateJobObject(None, '')
    info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
    info['BasicLimitInformation']['LimitFlags'] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)
    win32job.AssignProcessToJobObject(job, win32api.GetCurrentProcess())
    # Deliberate lifetime handle: Windows closes it at host process termination.
    return job.Detach()


def main():
    import servicemanager
    import win32service
    import win32serviceutil
    from runtime.remote_support_daemon import serve

    if len(sys.argv) != 2:
        raise ValueError('usage: remote_support_service.py ABSOLUTE_CONFIG')
    config = Path(sys.argv[1]).resolve()

    class WorkerService(win32serviceutil.ServiceFramework):
        _svc_name_ = 'CognitiveOSWorker'
        _svc_display_name_ = 'Cognitive OS file worker'

        def __init__(self, args):
            super().__init__(args)
            self.stop = threading.Event()

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING, waitHint=30000)
            self.stop.set()

        def SvcShutdown(self):
            self.SvcStop()

        def SvcDoRun(self):
            contain_process_tree()
            serve(config, self.stop)

    # Direct host: no PythonService registry import, post-install move or password.
    servicemanager.Initialize()
    servicemanager.PrepareToHostSingle(WorkerService)
    servicemanager.StartServiceCtrlDispatcher()


if __name__ == '__main__':
    main()
