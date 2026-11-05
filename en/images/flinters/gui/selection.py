from __future__ import annotations
from pathlib import Path
import json
import re
import sys
import tkinter as tk
from tkinter import filedialog, simpledialog, font as tkfont, messagebox, ttk
from typing import Callable
from flinters.tooltip import ToolTip, TooltipManager

class FlintSelection:
    """위젯 선택 상태와 바깥 클릭 해제를 공용으로 관리한다.

    개별 프로그램은 선택된 객체/필드를 이 클래스에 저장하고,
    선택 상태가 바뀔 때 실행할 콜백만 넘긴다.

    Tk의 일반 bind_all보다 먼저 실행되는 전용 bindtag를 사용하므로
    Entry/Combobox/Button 같은 위젯의 클래스 바인딩에 막히지 않는다.
    """

    def __init__(
        self,
        root: tk.Misc,
        *,
        inside_test: Callable[[tk.Misc], bool],
        on_change: Callable[[object | None, str | None], None] | None = None,
        default_field: str | None = None,
        tag_name: str | None = None,
    ) -> None:
        self.root = root
        self.inside_test = inside_test
        self.on_change = on_change
        self.default_field = default_field
        self.selected: object | None = None
        self.field: str | None = default_field
        self.tag_name = tag_name or f"FlintSelectionGuard_{id(self)}"

        root.bind_class(self.tag_name, "<Button-1>", self._on_global_click, add="+")
        self.install(root)

    def install(self, widget: tk.Misc) -> None:
        """현재 위젯과 모든 자식에 선택 감지 bindtag를 가장 먼저 삽입한다."""
        try:
            if widget.winfo_toplevel() is not self.root.winfo_toplevel():
                return

            tags = list(widget.bindtags())
            if self.tag_name not in tags:
                widget.bindtags((self.tag_name, *tags))

            for child in widget.winfo_children():
                self.install(child)
        except tk.TclError:
            return

    def select(self, item: object, field: str | None = None) -> None:
        """객체를 선택하고 선택 필드를 함께 저장한다."""
        self.selected = item
        self.field = self.default_field if field is None else field
        self._notify()

    def clear(self) -> None:
        """현재 선택을 해제한다."""
        if self.selected is None and self.field == self.default_field:
            return
        self.selected = None
        self.field = self.default_field
        self._notify()

    def _notify(self) -> None:
        if self.on_change is not None:
            self.on_change(self.selected, self.field)

    def _on_global_click(self, event) -> None:
        widget = getattr(event, "widget", None)
        if widget is None:
            return

        try:
            if widget.winfo_toplevel() is not self.root.winfo_toplevel():
                return
        except tk.TclError:
            return

        try:
            if self.inside_test(widget):
                return
        except (tk.TclError, AttributeError):
            return

        self.clear()
