from __future__ import annotations
from pathlib import Path
import json
import re
import sys
import tkinter as tk
from tkinter import filedialog, simpledialog, font as tkfont, messagebox, ttk
from typing import Callable
from flinters.tooltip import ToolTip, TooltipManager

class FlintNameColorEditor:
    """이름과 색상을 함께 편집하는 Flint 공용 GUI 도우미."""

    @staticmethod
    def foreground_for(master: tk.Misc, color: str) -> str:
        """배경색의 밝기를 기준으로 흰색/검정 글자색을 선택한다."""
        try:
            r16, g16, b16 = master.winfo_rgb(color)
            r, g, b = r16 / 257, g16 / 257, b16 / 257
            luminance = 0.299 * r + 0.587 * g + 0.114 * b
            return "black" if luminance >= 155 else "white"
        except tk.TclError:
            return "white"

    @classmethod
    def configure_label_style(
        cls,
        *,
        master: tk.Misc,
        style: ttk.Style,
        style_name: str,
        color: str,
        foreground: str = "",
    ) -> bool:
        """사용자 지정 배경색을 쓰는 ttk.Label 스타일을 등록한다."""
        color = str(color).strip()
        if not color:
            return False
        try:
            master.winfo_rgb(color)
        except tk.TclError:
            return False

        foreground = str(foreground).strip()
        if foreground:
            try:
                master.winfo_rgb(foreground)
            except tk.TclError:
                foreground = ""
        if not foreground:
            foreground = cls.foreground_for(master, color)

        style.configure(
            style_name,
            background=color,
            foreground=foreground,
            relief="flat",
            borderwidth=0,
        )
        return True

    @classmethod
    def show(
        cls,
        parent: tk.Misc,
        *,
        title: str,
        name_label: str,
        color_label: str,
        color_value_label: str,
        current_color_text: str,
        reset_text: str,
        save_text: str,
        cancel_text: str,
        invalid_color_text: str,
        initial_name: str,
        initial_color: str = "",
        reset_color: str = "",
        default_name: str = "",
        on_save: Callable | None = None,
        palette: tuple[str, ...] = (),
        text_color_label: str = "",
        text_color_value_label: str = "",
        initial_text_color: str = "",
        reset_text_color: str = "",
        text_palette: tuple[str, ...] = (),
        invalid_text_color_text: str = "",
    ) -> tk.Toplevel:
        """이름·배경색과 선택적으로 글자색까지 편집하는 범용 팝업을 연다."""
        popup = tk.Toplevel(parent)
        popup.title(title)
        popup.transient(parent)
        popup.resizable(False, False)
        popup.grab_set()

        frame = ttk.Frame(popup, padding=14)
        frame.pack(fill="both", expand=True)

        name_var = tk.StringVar(value=initial_name)
        effective_initial = initial_color.strip() or reset_color.strip()
        color_var = tk.StringVar(value=effective_initial)

        use_text_color = bool(text_color_label or text_color_value_label or text_palette or initial_text_color or reset_text_color)

        # 저장 의미(자동/명시)와 화면 미리보기 값을 분리한다.
        # 자동 상태에서도 입력칸에는 계산된 대비색을 보여주지만 저장값은 계속 ""이다.
        text_color_explicit = [bool(initial_text_color.strip())]
        effective_text_initial = initial_text_color.strip()
        if use_text_color and not effective_text_initial:
            effective_text_initial = cls.foreground_for(parent, effective_initial or _flint_style().TARGET)
        text_color_var = tk.StringVar(value=effective_text_initial)
        _text_preview_update = [False]

        palette_columns = max(len(palette) + 1, len(text_palette) + 1 if use_text_color else 0, 2)

        ttk.Label(frame, text=name_label).grid(row=0, column=0, sticky="w", pady=(0, 5))
        name_entry = ttk.Entry(frame, textvariable=name_var, width=30)
        name_entry.grid(row=1, column=0, columnspan=palette_columns, sticky="ew", pady=(0, 12))

        def make_palette_row(
            row: int,
            label: str,
            var: tk.StringVar,
            values: tuple[str, ...],
            current_color: str,
            style_prefix: str,
            on_pick: Callable[[str], None] | None = None,
        ) -> ttk.Button:
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=(0, 5))
            style_name = f"{style_prefix}.{id(popup)}.TButton"
            button = _flint_style().color_button(
                frame,
                text=current_color_text,
                color=current_color,
                command=lambda: None,
                style_name=style_name,
                width=max(8, len(current_color_text) + 2),
            )
            button.grid(row=row + 1, column=0, padx=(0, 4), pady=(0, 10), sticky="ew")
            for col, value in enumerate(values, start=1):
                def choose_color(c=value, v=var):
                    if on_pick is not None:
                        on_pick(c)
                    else:
                        v.set(c)

                _flint_style().color_button(
                    frame, text="", color=value,
                    command=choose_color,
                    width=2,
                ).grid(row=row + 1, column=col, padx=0, pady=(0, 10), sticky="ew")
            return button

        entry_span = max(palette_columns - 2, 1)
        text_current_button = None
        text_entry = None

        def set_explicit_text_color(value: str) -> None:
            text_color_explicit[0] = True
            text_color_var.set(value)

        # 글자색을 사용하는 편집기는 글자색을 먼저, 라벨(배경)색을 그 아래에 표시한다.
        if use_text_color:
            text_current_button = make_palette_row(
                2, text_color_label, text_color_var, text_palette,
                effective_text_initial or _flint_style().TEXT, "FlintCurrentTextColor",
                on_pick=set_explicit_text_color,
            )
            ttk.Label(frame, text=text_color_value_label).grid(row=4, column=0, sticky="w", pady=(0, 5))
            text_entry = ttk.Entry(frame, textvariable=text_color_var, width=18)
            text_entry.grid(row=5, column=0, columnspan=entry_span, sticky="ew")

            def mark_text_color_explicit(*_args):
                # 실제 값이 바뀐 경우에만 명시 글자색으로 전환한다.
                # 자동 미리보기/초기화에서 발생한 내부 변경은 제외한다.
                if not _text_preview_update[0]:
                    text_color_explicit[0] = True

            text_color_var.trace_add("write", mark_text_color_explicit)

            current_button = make_palette_row(
                6, color_label, color_var, palette,
                effective_initial or _flint_style().TARGET, "FlintCurrentColor"
            )
            ttk.Label(frame, text=color_value_label).grid(row=8, column=0, sticky="w", pady=(0, 5))
            color_entry = ttk.Entry(frame, textvariable=color_var, width=18)
            color_entry.grid(row=9, column=0, columnspan=entry_span, sticky="ew")
            next_row = 10
        else:
            current_button = make_palette_row(
                2, color_label, color_var, palette,
                effective_initial or _flint_style().TARGET, "FlintCurrentColor"
            )
            ttk.Label(frame, text=color_value_label).grid(row=4, column=0, sticky="w", pady=(0, 5))
            color_entry = ttk.Entry(frame, textvariable=color_var, width=18)
            color_entry.grid(row=5, column=0, columnspan=entry_span, sticky="ew")
            next_row = 6

        def reset_values() -> None:
            if default_name:
                name_var.set(default_name)
            color_var.set(reset_color)
            if use_text_color:
                # 초기화는 다시 자동 글자색(저장값 "")으로 복귀한다.
                text_color_explicit[0] = False
                _text_preview_update[0] = True
                try:
                    text_color_var.set(cls.foreground_for(parent, reset_color or _flint_style().TARGET))
                finally:
                    _text_preview_update[0] = False

        # 초기화 버튼은 마지막 색상값 행 오른쪽에 둔다.
        reset_row = 9 if use_text_color else 5
        _flint_style().button(
            frame, text=reset_text, command=reset_values,
            kind="warning", compact=True, width=7,
        ).grid(
            row=reset_row, column=entry_span,
            columnspan=max(palette_columns - entry_span, 1),
            padx=(8, 0), sticky="e"
        )

        def refresh_button(button: ttk.Button, style_name: str, color: str) -> None:
            try:
                parent.winfo_rgb(color)
            except tk.TclError:
                return
            style = ttk.Style(button)
            foreground = cls.foreground_for(parent, color)
            style.configure(
                style_name, background=color, foreground=foreground,
                relief="flat", borderwidth=0, bordercolor=color, lightcolor=color, darkcolor=color,
            )
            style.map(
                style_name,
                background=[("active", color), ("pressed", color)],
                foreground=[("!disabled", foreground)],
            )

        def refresh_current_color(*_args) -> None:
            background = color_var.get().strip() or reset_color.strip() or _flint_style().TARGET
            refresh_button(
                current_button, f"FlintCurrentColor.{id(popup)}.TButton",
                background
            )

            # 자동 상태에서는 배경색 변경에 맞춰 미리보기만 재계산한다.
            # 실제 저장 의미는 계속 자동("") 상태로 유지한다.
            if use_text_color and not text_color_explicit[0]:
                _text_preview_update[0] = True
                try:
                    text_color_var.set(cls.foreground_for(parent, background))
                finally:
                    _text_preview_update[0] = False

        def refresh_current_text_color(*_args) -> None:
            if text_current_button is not None:
                refresh_button(
                    text_current_button, f"FlintCurrentTextColor.{id(popup)}.TButton",
                    text_color_var.get().strip() or reset_text_color.strip() or _flint_style().TEXT
                )

        color_var.trace_add("write", refresh_current_color)
        if use_text_color:
            text_color_var.trace_add("write", refresh_current_text_color)

        buttons = ttk.Frame(frame)
        buttons.grid(row=next_row, column=0, columnspan=palette_columns, sticky="e", pady=(14, 0))

        def valid_color(value: str, entry: ttk.Entry | None, message: str) -> bool:
            if not value:
                return True
            try:
                parent.winfo_rgb(value)
                return True
            except tk.TclError:
                messagebox.showerror(title, message or invalid_color_text, parent=popup)
                if entry is not None:
                    entry.focus_set()
                return False

        def save_changes() -> None:
            cleaned_name = name_var.get().strip()
            if not cleaned_name or (default_name and cleaned_name == default_name):
                cleaned_name = ""

            cleaned_color = color_var.get().strip()
            if not valid_color(cleaned_color, color_entry, invalid_color_text):
                return
            stored_color = "" if reset_color and cleaned_color.lower() == reset_color.lower() else cleaned_color

            if use_text_color:
                cleaned_text = text_color_var.get().strip()
                if text_color_explicit[0] and not valid_color(cleaned_text, text_entry, invalid_text_color_text):
                    return

                # 자동 상태에서는 미리보기 계산색을 저장하지 않는다.
                # 사용자가 팔레트/직접 입력을 건드린 경우에만 명시 글자색을 저장한다.
                stored_text = cleaned_text if text_color_explicit[0] else ""
                if on_save is not None:
                    if on_save(cleaned_name, stored_color, stored_text) is False:
                        return
            elif on_save is not None:
                if on_save(cleaned_name, stored_color) is False:
                    return
            popup.destroy()

        _flint_style().button(
            buttons, text=cancel_text, command=popup.destroy, kind="muted", compact=True
        ).pack(side="right")
        _flint_style().button(
            buttons, text=save_text, command=save_changes, kind="sea", compact=True
        ).pack(side="right", padx=(0, 8))

        popup.bind("<Return>", lambda _event: save_changes())
        popup.bind("<Escape>", lambda _event: popup.destroy())
        name_entry.focus_set()
        name_entry.selection_range(0, "end")

        popup.update_idletasks()
        x = parent.winfo_rootx() + max((parent.winfo_width() - popup.winfo_width()) // 2, 0)
        y = parent.winfo_rooty() + max((parent.winfo_height() - popup.winfo_height()) // 2, 0)
        popup.geometry(f"+{x}+{y}")
        return popup


def _flint_style():
    from . import FlintStyle
    return FlintStyle
