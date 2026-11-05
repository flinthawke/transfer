from __future__ import annotations
from pathlib import Path
import json
import re
import sys
import tkinter as tk
from tkinter import filedialog, simpledialog, font as tkfont, messagebox, ttk
from typing import Callable
from flinters.tooltip import ToolTip, TooltipManager

from .state import FlintWindowState

class FlintWindowMixin:
    @staticmethod
    def _work_area(window: tk.Misc) -> tuple[int, int, int, int]:
        """작업 표시줄을 제외한 화면 영역. Windows 외 환경에서는 화면 전체 사용."""
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                rect = wintypes.RECT()
                if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
                    if rect.right > rect.left and rect.bottom > rect.top:
                        return rect.left, rect.top, rect.right, rect.bottom
            except (OSError, AttributeError, ValueError):
                pass
        return 0, 0, max(1, window.winfo_screenwidth()), max(1, window.winfo_screenheight())

    @classmethod
    def _fit_geometry(cls, window: tk.Misc, geometry: str) -> str | None:
        """저장된 크기·좌표를 현재 작업 영역으로 제한한다."""
        match = re.fullmatch(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)", geometry.strip())
        if match is None:
            return None
        left, top, right, bottom = cls._work_area(window)
        available_w, available_h = max(1, right - left), max(1, bottom - top)
        width = max(1, min(int(match[1]), available_w))
        height = max(1, min(int(match[2]), available_h))
        x = max(left, min(int(match[3]), right - width))
        y = max(top, min(int(match[4]), bottom - height))
        return f"{width}x{height}{x:+d}{y:+d}"

    @classmethod
    def setup_window(
        cls,
        window: tk.Tk | tk.Toplevel,
        *,
        title: str,
        size: str | tuple[int, int] | None = None,
        minsize: tuple[int, int] | None = None,
        icon: str | Path | None = None,
        resizable: tuple[bool, bool] = (True, True),
        center: bool = False,
        apply_style: bool = True,
    ) -> None:
        """주 창 최초 크기(작업 영역 가로 80%·세로 85%)와 작은 화면 방어를 공용 적용한다."""
        if apply_style:
            cls.apply(window)

        window.title(title)

        auto_size = size is None and isinstance(window, tk.Tk)
        left, top, right, bottom = cls._work_area(window)
        available_w, available_h = max(1, right - left), max(1, bottom - top)
        if auto_size:
            width = max(1, min(available_w, round(available_w * 0.80)))
            height = max(1, min(available_h, round(available_h * 0.85)))
            x = left + (available_w - width) // 2
            y = top + (available_h - height) // 2
            window.geometry(f"{width}x{height}{x:+d}{y:+d}")
        elif size is not None:
            if isinstance(size, tuple):
                window.geometry(f"{size[0]}x{size[1]}")
            else:
                window.geometry(size)

        if minsize is not None or auto_size:
            requested_w, requested_h = minsize if minsize is not None else (800, 500)
            window.minsize(min(max(1, requested_w), available_w),
                           min(max(1, requested_h), available_h))

        window.resizable(*resizable)

        if icon is not None:
            cls.set_icon(window, icon)

        if center and not auto_size:
            cls.center_window(window)

    @staticmethod
    def window_state(window: tk.Tk | tk.Toplevel, saved: dict | None = None):
        """공용 창 상태 저장·복원을 적용한다."""
        return FlintWindowState(window, saved)

    @staticmethod
    def center_window(window: tk.Tk | tk.Toplevel) -> None:
        """현재 창을 화면 중앙에 배치한다."""
        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = max((screen_width - width) // 2, 0)
        y = max((screen_height - height) // 2, 0)
        window.geometry(f"+{x}+{y}")

    @classmethod
    def center_child_window(cls, window: tk.Toplevel, parent: tk.Misc,
                            config_file: str | Path | None = None,
                            key: str | None = None) -> None:
        """기존 프로그램 설정 파일에 보조 창 위치를 저장하고 복원한다."""
        path = Path(config_file) if config_file is not None else None
        data = {}
        if path is not None and key:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    data = {}
            except (OSError, ValueError, UnicodeError):
                data = {}
        saved = data.get("child_windows", {}).get(key) if isinstance(data.get("child_windows"), dict) else None
        fitted = cls._fit_geometry(window, saved) if isinstance(saved, str) else None
        if fitted:
            window.geometry(fitted)
        else:
            parent.update_idletasks()
            window.update_idletasks()
            width, height = window.winfo_width(), window.winfo_height()
            x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
            left, top, right, bottom = cls._work_area(window)
            window.geometry(f"{max(left, min(x, right-width)):+d}"
                            f"{max(top, min(y, bottom-height)):+d}")
        if path is None or not key:
            return

        pending = [None]
        def save():
            pending[0] = None
            try:
                if not window.winfo_exists() or window.state() != "normal":
                    return
                current = {}
                try:
                    current = json.loads(path.read_text(encoding="utf-8"))
                    if not isinstance(current, dict):
                        current = {}
                except (OSError, ValueError, UnicodeError):
                    pass
                children = current.setdefault("child_windows", {})
                if not isinstance(children, dict):
                    children = current["child_windows"] = {}
                geometry = window.geometry()
                if children.get(key) != geometry:
                    children[key] = geometry
                    path.parent.mkdir(parents=True, exist_ok=True)
                    temp = path.with_suffix(".tmp")
                    temp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
                    temp.replace(path)
            except (OSError, tk.TclError):
                pass

        def changed(event):
            if event.widget is not window:
                return
            if pending[0] is not None:
                window.after_cancel(pending[0])
            pending[0] = window.after(600, save)

        window.bind("<Configure>", changed, add="+")
        window.bind("<Destroy>", lambda event: save() if event.widget is window else None, add="+")

    @staticmethod
    def set_icon(window: tk.Tk | tk.Toplevel, icon: str | Path) -> bool:
        """ICO 또는 PNG 아이콘을 적용한다. 실패 시 False를 반환한다."""
        icon_path = Path(icon)
        if not icon_path.exists():
            return False

        try:
            if icon_path.suffix.lower() == ".ico":
                window.iconbitmap(str(icon_path))
            else:
                image = tk.PhotoImage(file=str(icon_path))
                window.iconphoto(True, image)
                # PhotoImage가 가비지 컬렉션되지 않도록 창에 보관한다.
                setattr(window, "_flint_icon_image", image)
            return True
        except (tk.TclError, OSError):
            return False

