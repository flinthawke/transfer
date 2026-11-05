from __future__ import annotations
from pathlib import Path
import json
import re
import sys
import tkinter as tk
from tkinter import filedialog, simpledialog, font as tkfont, messagebox, ttk
from typing import Callable
from flinters.tooltip import ToolTip, TooltipManager

class FlintWindowState:
    """Flint 공용 창 상태 저장/복원 규칙.

    normal 상태의 geometry만 보존하며 저장된 창이 화면 밖에 있으면 복원 시 보정한다.
    """

    def __init__(self, window: tk.Tk | tk.Toplevel, saved: dict | None = None):
        self.window = window
        self._normal_geometry = self._safe_geometry()
        self._last_non_iconic_state = "normal"
        window.bind("<Configure>", self._on_configure, add="+")
        self.restore(saved)

    def _safe_state(self) -> str:
        try:
            state = str(self.window.state())
        except tk.TclError:
            return "normal"
        return state if state in {"normal", "zoomed", "iconic"} else "normal"

    def _safe_geometry(self) -> str:
        try:
            return str(self.window.geometry())
        except tk.TclError:
            return ""

    def _remember_normal_geometry(self) -> None:
        if self._safe_state() != "normal":
            return
        geometry = self._safe_geometry()
        if geometry:
            self._normal_geometry = geometry
        self._last_non_iconic_state = "normal"

    def _on_configure(self, _event=None) -> None:
        state = self._safe_state()
        if state == "normal":
            self._remember_normal_geometry()
        elif state == "zoomed":
            self._last_non_iconic_state = "zoomed"

    def restore(self, saved: dict | None) -> None:
        """저장값이 있을 때만 적용하고, 없으면 프로그램의 최초 창값을 그대로 둔다."""
        if not isinstance(saved, dict):
            saved = {}

        geometry = saved.get("geometry")
        if isinstance(geometry, str) and geometry.strip():
            try:
                safe_geometry = _flint_style()._fit_geometry(self.window, geometry)
                if safe_geometry is not None:
                    self.window.geometry(safe_geometry)
                    self._normal_geometry = safe_geometry
            except tk.TclError:
                pass
        else:
            self._remember_normal_geometry()

        if str(saved.get("state", "normal")) == "zoomed":
            self._last_non_iconic_state = "zoomed"

            def apply_zoomed():
                try:
                    if self.window.winfo_exists():
                        self.window.state("zoomed")
                except tk.TclError:
                    pass

            self.window.after_idle(apply_zoomed)
        else:
            self._last_non_iconic_state = "normal"

    def snapshot(self) -> dict[str, str]:
        """설정 파일에 저장할 normal geometry와 창 상태를 반환한다."""
        state = self._safe_state()
        if state == "normal":
            self._remember_normal_geometry()
            saved_state = "normal"
        elif state == "zoomed":
            self._last_non_iconic_state = "zoomed"
            saved_state = "zoomed"
        else:
            # 최소화 자체는 저장하지 않고 최소화 직전의 normal/zoomed 상태를 유지한다.
            saved_state = self._last_non_iconic_state

        return {
            "geometry": self._normal_geometry or self._safe_geometry(),
            "state": saved_state,
        }


def _flint_style():
    from . import FlintStyle
    return FlintStyle
