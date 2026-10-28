"""Windows-owned child processes; IDE hard-stop closes the job and its descendants."""

import ctypes
import os
import subprocess
import sys
import uuid
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BasicLimits(ctypes.Structure):
    _fields_ = [
        ("process_time", ctypes.c_longlong),
        ("job_time", ctypes.c_longlong),
        ("flags", wintypes.DWORD),
        ("min_working_set", ctypes.c_size_t),
        ("max_working_set", ctypes.c_size_t),
        ("active_processes", wintypes.DWORD),
        ("affinity", ctypes.c_size_t),
        ("priority", wintypes.DWORD),
        ("scheduling", wintypes.DWORD),
    ]


class IoCounters(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_ulonglong)
        for name in (
            "read_ops",
            "write_ops",
            "other_ops",
            "read_bytes",
            "write_bytes",
            "other_bytes",
        )
    ]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("basic", BasicLimits),
        ("io", IoCounters),
        ("process_memory", ctypes.c_size_t),
        ("job_memory", ctypes.c_size_t),
        ("peak_process_memory", ctypes.c_size_t),
        ("peak_job_memory", ctypes.c_size_t),
    ]


class OwnedChildren:
    def __init__(self):
        if os.name != "nt":
            raise RuntimeError("The one-click launcher currently supports Windows only")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            "SetInformationJobObject": (
                [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD],
                wintypes.BOOL,
            ),
            "OpenProcess": (
                [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD],
                wintypes.HANDLE,
            ),
            "AssignProcessToJobObject": (
                [wintypes.HANDLE, wintypes.HANDLE],
                wintypes.BOOL,
            ),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = args, result
        self.name = "Local\\SilverEconomy-" + uuid.uuid4().hex
        self.handle = self.kernel.CreateJobObjectW(None, self.name)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(
            self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error
        self.processes = []

    def start(self, action, env):
        # The helper cannot spawn anything before its parent assigns the job.
        # If the parent dies early, stdin reaches EOF and the helper exits.
        process = subprocess.Popen(
            [
                sys.executable,
                "-u",
                str(ROOT / "scripts/dev_child.py"),
                action,
                self.name,
            ],
            cwd=ROOT,
            env=env,
            stdin=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        handle = self.kernel.OpenProcess(
            0x0101, False, process.pid
        )  # SET_QUOTA | TERMINATE
        try:
            if not handle or not self.kernel.AssignProcessToJobObject(
                self.handle, handle
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            self.processes.append(process)
            process.stdin.write(b"start\n")
            process.stdin.flush()
        except BaseException:
            process.terminate()
            process.wait(timeout=5)
            raise
        finally:
            process.stdin.close()
            if handle:
                self.kernel.CloseHandle(handle)
        return process

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
        for process in getattr(self, "processes", []):
            process.wait(timeout=10)


def join_job(name):
    """Join from the actual interpreter too: Windows venv exe can be a redirector."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenJobObjectW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.OpenJobObjectW.restype = wintypes.HANDLE
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.IsProcessInJob.argtypes = [
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.BOOL),
    ]
    kernel.IsProcessInJob.restype = wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenJobObjectW(0x0005, False, name)  # ASSIGN_PROCESS | QUERY
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        current, member = kernel.GetCurrentProcess(), wintypes.BOOL()
        if not kernel.IsProcessInJob(current, handle, ctypes.byref(member)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not member.value and not kernel.AssignProcessToJobObject(handle, current):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(handle)
