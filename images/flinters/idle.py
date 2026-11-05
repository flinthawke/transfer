"""Flint 계열 저장소 Idle 감지 공용 모듈.

백업/미러 작업이 동기화 중인 원격·가상 저장소와 충돌하지 않도록
대상 저장소를 판별하고 Busy/Idle 상태를 확인한 뒤 안정될 때까지 기다린다.
UI를 직접 다루지 않으며 상태 표시는 콜백으로 호출자에게 전달한다.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

# ============================================================
# 저장소 Idle 감지 / Google Drive 상태 판정
# ============================================================

@dataclass(frozen=True)
class IdleTargetInfo:
    provider: str = "local"
    sync_sensitive: bool = False
    root: Path | None = None
    label: str = ""


_GOOGLE_PROCESS_NAMES = {
    "googledrivefs.exe",
    "googledrivefs",
}


if os.name == "nt":
    TH32CS_SNAPPROCESS = 0x00000002
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]



# ============================================================
# 저장소 및 Google Drive 판별
# ============================================================

def _windows_volume_label(path: Path) -> tuple[Path | None, str]:
    """Windows 경로의 드라이브 루트와 볼륨 레이블을 가져온다."""
    if os.name != "nt":
        return None, ""

    drive, _tail = os.path.splitdrive(str(path))
    if not drive:
        return None, ""

    root = Path(drive + "\\")
    volume_name = ctypes.create_unicode_buffer(261)
    fs_name = ctypes.create_unicode_buffer(261)
    serial = wintypes.DWORD()
    max_component = wintypes.DWORD()
    flags = wintypes.DWORD()

    try:
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            str(root),
            volume_name,
            len(volume_name),
            ctypes.byref(serial),
            ctypes.byref(max_component),
            ctypes.byref(flags),
            fs_name,
            len(fs_name),
        )
    except Exception:
        return root, ""

    return root, volume_name.value.strip() if ok else ""


def _google_drive_pids() -> list[int]:
    """현재 실행 중인 Google Drive for desktop 프로세스 PID를 찾는다."""
    if os.name != "nt":
        return []

    kernel32 = ctypes.windll.kernel32
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        return []

    result: list[int] = []
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)

    try:
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            name = str(entry.szExeFile).casefold()
            if name in _GOOGLE_PROCESS_NAMES:
                result.append(int(entry.th32ProcessID))
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)

    return result


def _google_drive_running() -> bool:
    return bool(_google_drive_pids())


def inspect_target(path: Path | str) -> IdleTargetInfo:
    """백업 대상이 어떤 저장소인지 보수적으로 판별한다.

    현재는 Google Drive for desktop만 동기화 민감 저장소로 구분한다.
    다른 저장소는 기존 백업 동작을 그대로 유지한다.
    """
    candidate = Path(path)
    root, label = _windows_volume_label(candidate)
    label_key = label.casefold().replace(" ", "")

    if "googledrive" in label_key:
        return IdleTargetInfo(
            provider="google_drive",
            sync_sensitive=True,
            root=root,
            label=label,
        )

    # 일부 DriveFS 버전/설정에서는 볼륨 레이블 조회가 비어 있을 수 있다.
    # 이 경우 DriveFS가 실제 실행 중이고 드라이브 최상위 폴더가 Google Drive의
    # 대표 구조(My Drive / Shared drives)일 때만 보조 판정을 사용한다.
    if _google_drive_running() and root is not None:
        try:
            relative = candidate.resolve(strict=False).relative_to(root.resolve(strict=False))
            first = relative.parts[0].casefold() if relative.parts else ""
        except (OSError, ValueError):
            first = ""
        if first in {"my drive", "shared drives", "내 드라이브", "공유 드라이브"}:
            return IdleTargetInfo(
                provider="google_drive",
                sync_sensitive=True,
                root=root,
                label=label,
            )

    return IdleTargetInfo(provider="local", sync_sensitive=False, root=root, label=label)



# ============================================================
# Google Drive 작업 상태 감지
# ============================================================

def _process_io_total(pid: int) -> int | None:
    """Windows 프로세스의 누적 파일 읽기/쓰기 바이트를 반환한다."""
    if os.name != "nt":
        return None

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return None

    counters = IO_COUNTERS()
    try:
        if not kernel32.GetProcessIoCounters(handle, ctypes.byref(counters)):
            return None
        return int(counters.ReadTransferCount + counters.WriteTransferCount)
    finally:
        kernel32.CloseHandle(handle)


def _drivefs_io_total() -> int | None:
    """DriveFS 프로세스들의 누적 실제 파일 I/O 바이트를 합산한다."""
    pids = _google_drive_pids()
    if not pids:
        return None

    total = 0
    readable = False
    for pid in pids:
        value = _process_io_total(pid)
        if value is None:
            continue
        total += value
        readable = True
    return total if readable else None


def google_drive_is_busy(
    *,
    sample_seconds: float = 1.0,
    busy_bytes_per_second: int = 512 * 1024,
    cancelled: Callable[[], bool] | None = None,
) -> bool:
    """DriveFS의 짧은 I/O 변화량으로 현재 적극적인 동기화 활동을 감지한다.

    네트워크 서버 상태를 추측하는 대신 DriveFS가 실제 파일을 읽고 쓰는지를 본다.
    아주 작은 인덱스/상태 갱신은 동기화로 오인하지 않도록 임계값 이하를 무시한다.
    """
    before = _drivefs_io_total()
    if before is None:
        return False

    interval = max(float(sample_seconds), 0.1)
    deadline = time.monotonic() + interval
    while time.monotonic() < deadline:
        if cancelled and cancelled():
            return False
        time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))

    after = _drivefs_io_total()
    if after is None or after < before:
        return False

    rate = (after - before) / interval
    return rate >= max(int(busy_bytes_per_second), 1)

def wait_for_idle(
    destinations: Iterable[Path | str],
    *,
    cancel_event,
    on_wait: Callable[[str], None] | None = None,
    on_progress: Callable[[str, float, float | None], None] | None = None,
    on_wait_limit: Callable[[str, float], bool] | None = None,
    wait_limit_seconds: float | None = None,
    on_clear: Callable[[], None] | None = None,
    log_callback: Callable[[str], None] | None = None,
    stable_rounds: int = 3,
    sample_seconds: float = 1.0,
    busy_bytes_per_second: int = 512 * 1024,
) -> bool:
    """동기화 민감 저장소가 안정될 때까지 기다린다.

    이 함수는 UI에 의존하지 않는다. 대기 상태 표시는 ``on_wait``에 대상 표시 문자열을
    전달하고, ``on_progress``에는 대상·경과시간·대기 한도를 전달한다. ``wait_limit_seconds``
    이후에도 Busy이면 ``on_wait_limit``의 결정(True=계속, False=중단)을 따른다.
    종료 시에는 ``on_clear``를 호출하고 취소되거나 사용자가 중단을 선택하면 False를 반환한다.
    """
    sensitive: dict[tuple[str, str], IdleTargetInfo] = {}
    for destination in destinations:
        info = inspect_target(destination)
        if not info.sync_sensitive:
            continue
        root_text = str(info.root or Path(destination))
        sensitive[(info.provider, os.path.normcase(root_text))] = info

    if not sensitive:
        return True

    required = max(int(stable_rounds), 1)
    try:
        for info in sensitive.values():
            stable = 0
            display_path = str(info.root or "Google Drive")
            wait_started = time.monotonic()
            limit = None if wait_limit_seconds is None else max(float(wait_limit_seconds), 0.1)

            while stable < required:
                if cancel_event.is_set():
                    return False

                elapsed = time.monotonic() - wait_started
                if on_wait is not None:
                    on_wait(display_path)
                if on_progress is not None:
                    on_progress(display_path, elapsed, limit)

                busy = google_drive_is_busy(
                    sample_seconds=sample_seconds,
                    busy_bytes_per_second=busy_bytes_per_second,
                    cancelled=cancel_event.is_set,
                )
                if cancel_event.is_set():
                    return False

                elapsed = time.monotonic() - wait_started
                if on_progress is not None:
                    on_progress(display_path, elapsed, limit)

                if busy:
                    stable = 0
                    if log_callback:
                        log_callback(f"Google Drive sync activity detected: {display_path}")

                    if limit is not None and elapsed >= limit and on_wait_limit is not None:
                        if not on_wait_limit(display_path, elapsed):
                            return False
                        # 계속 기다리기를 선택하면 다음 선택 시점까지 다시 limit만큼 기다린다.
                        wait_started = time.monotonic()
                else:
                    stable += 1

            if log_callback:
                log_callback(f"Google Drive idle: {display_path}")
        return True
    finally:
        if on_clear is not None:
            on_clear()


# ============================================================
# 범용 작업 안정화 검사 (기존 Google Drive API와 독립)
# ============================================================

@dataclass(frozen=True)
class IdleProbe:
    """호출자가 제공하는 작업 대상 상태 검사기.

    check는 True=busy, False=idle, None=판정 불가를 반환한다.
    물리 디스크의 안전성(마운트/잠금/시스템 디스크 여부)은 별도로 검사해야 한다.
    """
    label: str
    check: Callable[[], bool | None]


def wait_for_probes(
    probes: Iterable[IdleProbe],
    *,
    cancel_event,
    stable_rounds: int = 3,
    sample_seconds: float = 1.0,
    wait_limit_seconds: float | None = None,
    on_wait: Callable[[str], None] | None = None,
    on_progress: Callable[[str, float, float | None], None] | None = None,
    on_wait_limit: Callable[[str, float], bool] | None = None,
    on_clear: Callable[[], None] | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> bool:
    """범용 Busy/Idle 감지기들이 연속 안정 상태인지 확인한다.

    판정 불가(None), 감지기 오류는 안전하게 실패(False) 처리한다.
    타임아웃 후 계속 대기하려면 on_wait_limit이 명시적으로 허용해야 한다.
    작업 스레드에서 호출하고 Tk UI 갱신은 호출자가 이벤트 큐로 전달한다.
    """
    targets = tuple(probes)
    required = max(1, int(stable_rounds))
    interval = max(0.1, float(sample_seconds))
    limit = None if wait_limit_seconds is None else max(0.1, float(wait_limit_seconds))
    try:
        for probe in targets:
            stable = 0
            started = time.monotonic()
            while stable < required:
                if cancel_event.is_set():
                    return False
                elapsed = time.monotonic() - started
                if on_wait:
                    on_wait(probe.label)
                if on_progress:
                    on_progress(probe.label, elapsed, limit)
                try:
                    busy = probe.check()
                except Exception as exc:
                    if log_callback:
                        log_callback(f"Idle probe failed ({probe.label}): {exc}")
                    return False
                if busy is None:
                    if log_callback:
                        log_callback(f"Idle probe unavailable: {probe.label}")
                    return False
                if busy:
                    stable = 0
                    if log_callback:
                        log_callback(f"Busy: {probe.label}")
                else:
                    stable += 1
                if stable >= required:
                    break
                elapsed = time.monotonic() - started
                if limit is not None and elapsed >= limit:
                    if on_wait_limit is None or not on_wait_limit(probe.label, elapsed):
                        return False
                    started = time.monotonic()
                if cancel_event.wait(interval):
                    return False
            if log_callback:
                log_callback(f"Idle: {probe.label}")
        return True
    finally:
        if on_clear:
            on_clear()
