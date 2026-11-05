"""Flint Toolbox external restart helper (Windows / Python source / Nuitka)."""
from __future__ import annotations

import base64
import ctypes
import json
import os
import subprocess
import sys
from pathlib import Path


def _wait_for_exit(pid: int) -> None:
    """Wait for the original process, not a guessed fixed delay."""
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
    kernel32.WaitForSingleObject.restype = ctypes.c_ulong
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_int
    SYNCHRONIZE = 0x00100000
    INFINITE = 0xFFFFFFFF
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error == 87:  # ERROR_INVALID_PARAMETER: process already gone
            return
        raise OSError(error, f'OpenProcess failed for PID {pid}')
    try:
        result = kernel32.WaitForSingleObject(handle, INFINITE)
        if result != 0:
            raise OSError(f'WaitForSingleObject failed: {result}')
    finally:
        kernel32.CloseHandle(handle)


def _run_source_helper(payload: str) -> None:
    data = json.loads(base64.urlsafe_b64decode(payload.encode('ascii')).decode('utf-8'))
    _wait_for_exit(int(data['pid']))
    env = os.environ.copy()
    for key in ('NUITKA_ONEFILE_PARENT', 'NUITKA_ONEFILE_BINARY'):
        env.pop(key, None)
    subprocess.Popen(
        [data['executable'], *data['args']], cwd=data['cwd'], env=env,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True,
    )


def _ps_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _request_compiled_restart(executable: str, args: list[str], cwd: str, parent_pid: int) -> None:
    """Compiled programs have no guaranteed Python runtime; retain native PowerShell helper."""
    arguments = subprocess.list2cmdline(args)
    script = f"""
$ErrorActionPreference = 'Stop'
$targetProcessId = {parent_pid}
$program = {_ps_literal(executable)}
$arguments = {_ps_literal(arguments)}
$workdir = {_ps_literal(cwd)}
try {{
    $oldProcess = Get-Process -Id $targetProcessId -ErrorAction SilentlyContinue
    if ($null -ne $oldProcess) {{ $oldProcess.WaitForExit() }}
    $start = New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName = $program
    $start.Arguments = $arguments
    $start.WorkingDirectory = $workdir
    $start.UseShellExecute = $false
    $child = [System.Diagnostics.Process]::Start($start)
    if ($null -eq $child) {{ throw 'Process.Start returned null' }}
}} catch {{
    exit 1
}}
"""
    encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    env = os.environ.copy()
    for key in ('NUITKA_ONEFILE_PARENT', 'NUITKA_ONEFILE_BINARY'):
        env.pop(key, None)
    helper = subprocess.Popen(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-EncodedCommand', encoded],
        cwd=cwd, env=env,
        creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    try:
        exit_code = helper.wait(timeout=0.3)
    except subprocess.TimeoutExpired:
        pass
    else:
        if exit_code != 0:
            raise OSError(f'Restart helper exited early with code {exit_code}')


def _close_application() -> None:
    """Request normal Tk window closure after the restart helper is ready."""
    import tkinter as tk

    root = getattr(tk, '_default_root', None)
    if root is None:
        raise RuntimeError('No Tk root found; application must provide its own close procedure')

    def close_window() -> None:
        try:
            callback = root.protocol('WM_DELETE_WINDOW')
            if callback:
                root.tk.call(callback)
            else:
                root.destroy()
        except tk.TclError:
            pass

    root.after_idle(close_window)


def request_restart() -> None:
    """Launch an external helper and request normal Tk application closure."""
    if os.name != 'nt':
        raise OSError('Windows is required for restart')
    main = sys.modules.get('__main__')
    compiled = bool(getattr(sys, 'frozen', False) or getattr(main, '__compiled__', None))
    onefile = os.environ.get('NUITKA_ONEFILE_BINARY')
    if onefile or compiled:
        compiled = True
        # Nuitka Onefile may set sys.executable to its temporary unpacked
        # python.exe. sys.argv[0] identifies the original launched EXE.
        candidates = [sys.argv[0], onefile]
        executable_path = None
        for candidate in candidates:
            if not candidate:
                continue
            path = Path(candidate).resolve()
            if path.is_file() and path.suffix.lower() == '.exe' and not (
                path.name.lower() == 'python.exe'
                and any(part.lower().startswith('onefile_') for part in path.parts)
            ):
                executable_path = path
                break
        if executable_path is None:
            raise OSError('Cannot locate original compiled EXE for restart')
        executable = str(executable_path)
        args = sys.argv[1:]
    else:
        executable = str(Path(sys.executable).resolve())
        args = [str(Path(sys.argv[0]).resolve()), *sys.argv[1:]]
    cwd = str(Path.cwd())
    pid = os.getpid()
    if compiled:
        _request_compiled_restart(executable, args, cwd, pid)
        _close_application()
        return
    payload = base64.urlsafe_b64encode(json.dumps({
        'pid': pid, 'executable': executable, 'args': args, 'cwd': cwd,
    }).encode('utf-8')).decode('ascii')
    helper = subprocess.Popen(
        [executable, str(Path(__file__).resolve()), '--restart-helper', payload],
        cwd=cwd,
        creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    _close_application()


if __name__ == '__main__' and len(sys.argv) == 3 and sys.argv[1] == '--restart-helper':
    _run_source_helper(sys.argv[2])
