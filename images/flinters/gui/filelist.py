from __future__ import annotations
from pathlib import Path
import json
import re
import sys
import tkinter as tk
from tkinter import filedialog, simpledialog, font as tkfont, messagebox, ttk
from typing import Callable
from flinters.tooltip import ToolTip, TooltipManager

class FlintFileList(ttk.Frame):
    """여러 파일을 깔끔하게 표시하고 추가/제거하는 Flint 공용 목록 위젯.

    프로그램은 파일의 실제 추가/삭제 로직만 콜백으로 넘긴다.
    표현은 Flint Treeview/버튼/스크롤 규격을 공통으로 사용한다.
    """

    def __init__(
        self,
        master,
        *,
        on_add: Callable[[], None] | None = None,
        on_remove: Callable[[object], None] | None = None,
        on_remove_many: Callable[[list[object]], None] | None = None,
        height: int = 5,
        add_text: str = "파일 추가",
        empty_text: str = "등록된 파일이 없습니다.",
    ) -> None:
        super().__init__(master)
        self.on_add = on_add
        self.on_remove = on_remove
        self.on_remove_many = on_remove_many
        self.empty_text = empty_text
        self._payloads: dict[str, object] = {}

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        top.columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value=empty_text)
        ttk.Label(
            top,
            textvariable=self.status_var,
            foreground=_flint_style().SUBTEXT,
        ).grid(row=0, column=0, sticky="w")

        self.add_button = _flint_style().button(
            top,
            text=add_text,
            command=self._add,
            kind="emerald",
            compact=True,
        )
        self.add_button.grid(row=0, column=1, padx=(8, 0))

        self.remove_button = _flint_style().button(
            top,
            text="×",
            command=self._remove,
            kind="danger",
            compact=True,
            width=3,
        )
        self.remove_button.grid(row=0, column=2, padx=(5, 0))

        body = ttk.Frame(self)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            body,
            columns=("state", "name"),
            show="headings",
            height=max(2, int(height)),
            selectmode="extended",
            style="FlintFileList.Treeview",
        )
        self.tree.heading("state", text="상태")
        self.tree.heading("name", text="파일")
        self.tree.column("state", width=86, minwidth=72, stretch=False, anchor="center")
        self.tree.column("name", width=360, minwidth=180, stretch=True, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(
            yscrollcommand=_flint_style().auto_hide_scrollbar(scroll)
        )

        self.tree.bind("<Delete>", lambda _event: self._remove(), add="+")
        self.tree.bind("<Double-1>", lambda _event: None, add="+")
        self._update_remove_state()

        self.tree.bind(
            "<<TreeviewSelect>>",
            lambda _event: self._update_remove_state(),
            add="+",
        )

    def _add(self) -> None:
        if self.on_add is not None:
            self.on_add()

    def _remove(self) -> None:
        payloads = self.selected_payloads()
        if not payloads:
            return

        if len(payloads) > 1 and self.on_remove_many is not None:
            self.on_remove_many(payloads)
            return

        if self.on_remove is not None:
            self.on_remove(payloads[0])

    def _update_remove_state(self) -> None:
        if self.tree.selection():
            self.remove_button.state(["!disabled"])
        else:
            self.remove_button.state(["disabled"])

    def set_rows(
        self,
        rows: list[tuple[str, str, object]],
        *,
        status_text: str | None = None,
    ) -> None:
        """(상태, 표시명, payload) 목록으로 화면을 다시 그린다."""
        previous_payloads = {
            self._payloads[iid]
            for iid in self.tree.selection()
            if iid in self._payloads
        }

        self.tree.delete(*self.tree.get_children())
        self._payloads.clear()

        restored_iids: list[str] = []
        for index, (state, name, payload) in enumerate(rows):
            iid = f"row-{index}"
            self.tree.insert("", "end", iid=iid, values=(state, name))
            self._payloads[iid] = payload
            if payload in previous_payloads:
                restored_iids.append(iid)

        if restored_iids:
            self.tree.selection_set(restored_iids)
            self.tree.see(restored_iids[0])

        if status_text is not None:
            self.status_var.set(status_text)
        elif rows:
            self.status_var.set(f"파일 {len(rows)}개")
        else:
            self.status_var.set(self.empty_text)

        self._update_remove_state()

    def selected_payload(self):
        selection = self.tree.selection()
        if not selection:
            return None
        return self._payloads.get(selection[0])

    def selected_payloads(self) -> list[object]:
        """현재 선택된 모든 행의 payload를 선택 순서대로 반환한다."""
        return [
            self._payloads[iid]
            for iid in self.tree.selection()
            if iid in self._payloads
        ]


def _flint_style():
    from . import FlintStyle
    return FlintStyle
