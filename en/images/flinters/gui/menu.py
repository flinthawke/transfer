from __future__ import annotations
from pathlib import Path
import json
import re
import sys
import tkinter as tk
from tkinter import filedialog, simpledialog, font as tkfont, messagebox, ttk
from typing import Callable
from flinters.tooltip import ToolTip, TooltipManager

class FlintMenuMixin:
    @classmethod
    def make_menu_bar(cls, master: tk.Misc) -> tk.Frame:
        """Flint 테마를 따르는 얇은 공용 메뉴바를 만든다."""
        bar = tk.Frame(
            master,
            background=cls.BACKGROUND,
            bd=0,
            highlightthickness=0,
            height=26,
        )
        bar.pack(side="top", fill="x")
        bar.pack_propagate(False)
        return bar

    @classmethod
    def add_menu_command(
        cls,
        menu_bar: tk.Frame,
        *,
        text: str,
        command: Callable[[], None] | None = None,
    ) -> tk.Label:
        """Flint 메뉴바에서 드롭다운 없이 바로 실행되는 메뉴 항목을 만든다."""
        label = tk.Label(
            menu_bar,
            text=text,
            font=cls.NORMAL_FONT,
            background=cls.BACKGROUND,
            foreground=cls.TEXT,
            bd=0,
            highlightthickness=0,
            padx=8,
            pady=0,
            anchor="w",
            cursor="hand2",
        )
        label.pack(side="left", fill="y")

        def enter(_event=None):
            label.configure(background=cls.NOTEBOOK_TAB_ACTIVE, foreground=cls.TEXT)

        def leave(_event=None):
            label.configure(background=cls.BACKGROUND, foreground=cls.TEXT)

        def activate(_event=None):
            if command is not None:
                command()
            return "break"

        label.bind("<Button-1>", activate)
        label.bind("<Enter>", enter)
        label.bind("<Leave>", leave)
        return label

    @classmethod
    def add_menu_button(
        cls,
        menu_bar: tk.Frame,
        *,
        text: str,
        items: list[dict],
    ) -> tk.Label:
        """Flint 위젯만 사용해 라이트/다크 테마를 따르는 드롭다운 메뉴를 만든다."""
        label = tk.Label(
            menu_bar,
            text=text,
            font=cls.NORMAL_FONT,
            background=cls.BACKGROUND,
            foreground=cls.TEXT,
            bd=0,
            highlightthickness=0,
            padx=8,
            pady=0,
            anchor="w",
            cursor="arrow",
        )
        label.pack(side="left", fill="y")

        popup: tk.Toplevel | None = None

        def close_popup(_event=None):
            nonlocal popup
            if popup is not None:
                try:
                    if popup.winfo_exists():
                        popup.destroy()
                except tk.TclError:
                    pass
                popup = None
            try:
                label.configure(background=cls.BACKGROUND, foreground=cls.TEXT)
            except tk.TclError:
                pass

        def open_popup(_event=None):
            nonlocal popup

            if popup is not None:
                close_popup()
                return "break"

            popup = tk.Toplevel(label)
            popup.withdraw()
            popup.overrideredirect(True)
            popup.configure(background=cls.BORDER, bd=0)

            panel = tk.Frame(
                popup,
                background=cls.PANEL,
                bd=0,
                highlightthickness=1,
                highlightbackground=cls.BORDER,
                highlightcolor=cls.BORDER,
            )
            panel.pack(fill="both", expand=True)

            def add_row(
                row_text: str,
                command: Callable[[], None] | None = None,
                *,
                variable: tk.Variable | None = None,
                disabled: bool = False,
            ):
                row = tk.Label(
                    panel,
                    text="",
                    font=cls.NORMAL_FONT,
                    background=cls.PANEL,
                    foreground=cls.SUBTEXT if disabled else cls.TEXT,
                    anchor="w",
                    padx=10,
                    pady=5,
                    cursor="arrow" if disabled else "hand2",
                )
                row.pack(fill="x")

                def refresh_text(*_args):
                    prefix = ""
                    if variable is not None:
                        try:
                            prefix = "☑ " if bool(variable.get()) else "☐ "
                        except tk.TclError:
                            prefix = "☐ "
                    row.configure(text=prefix + row_text)

                refresh_text()

                if disabled:
                    return

                def enter(_e=None):
                    row.configure(
                        background=cls.NOTEBOOK_TAB_ACTIVE,
                        foreground=cls.TEXT,
                    )

                def leave(_e=None):
                    row.configure(
                        background=cls.PANEL,
                        foreground=cls.TEXT,
                    )

                def activate(_e=None):
                    if variable is not None:
                        variable.set(not bool(variable.get()))
                    close_popup()
                    if command is not None:
                        command()
                    return "break"

                row.bind("<Enter>", enter)
                row.bind("<Leave>", leave)
                row.bind("<Button-1>", activate)

            for item in items:
                kind = item.get("type", "command")
                if kind == "separator":
                    sep = tk.Frame(panel, background=cls.BORDER, height=1, bd=0)
                    sep.pack(fill="x", padx=4, pady=2)
                elif kind == "checkbutton":
                    add_row(
                        item["label"],
                        item.get("command"),
                        variable=item["variable"],
                        disabled=item.get("state") == "disabled",
                    )
                else:
                    add_row(
                        item["label"],
                        item.get("command"),
                        disabled=item.get("state") == "disabled",
                    )

            popup.update_idletasks()
            x = label.winfo_rootx()
            y = label.winfo_rooty() + label.winfo_height()
            popup.geometry(f"+{x}+{y}")
            popup.deiconify()
            popup.lift()

            label.configure(
                background=cls.NOTEBOOK_TAB_ACTIVE,
                foreground=cls.TEXT,
            )

            def on_focus_out(_e=None):
                try:
                    popup.after(20, lambda: close_popup() if popup is not None else None)
                except tk.TclError:
                    pass

            popup.bind("<Escape>", close_popup)
            popup.bind("<FocusOut>", on_focus_out)
            popup.focus_force()
            return "break"

        def enter(_event=None):
            if popup is None:
                label.configure(background=cls.NOTEBOOK_TAB_ACTIVE, foreground=cls.TEXT)

        def leave(_event=None):
            if popup is None:
                label.configure(background=cls.BACKGROUND, foreground=cls.TEXT)

        label.bind("<Button-1>", open_popup)
        label.bind("<Enter>", enter)
        label.bind("<Leave>", leave)
        return label

    @classmethod
    def make_popup_panel(cls, owner: tk.Misc) -> tuple[tk.Toplevel, tk.Frame]:
        """공용 메뉴 팝업의 테마 테두리와 내용 패널을 만든다."""
        popup = tk.Toplevel(owner)
        popup.withdraw()
        popup.overrideredirect(True)
        popup.configure(background=cls.BORDER, bd=0)
        panel = tk.Frame(popup, background=cls.PANEL, bd=0, padx=1, pady=1)
        panel.pack(fill="both", expand=True, padx=1, pady=1)
        return popup, panel

    @classmethod
    def make_context_menu(cls, owner: tk.Misc) -> tk.Menu:
        """공용 라이트/다크 테마를 따르는 우클릭 메뉴를 만든다."""
        return tk.Menu(
            owner, tearoff=False,
            background=cls.PANEL, foreground=cls.TEXT,
            activebackground=cls.NOTEBOOK_TAB_ACTIVE,
            activeforeground=cls.TEXT, disabledforeground=cls.SUBTEXT,
            selectcolor=cls.SEA, relief="solid", borderwidth=1,
            activeborderwidth=0,
        )

    @classmethod
    def add_check_menu_item(
        cls,
        menu: tk.Menu,
        *,
        label: str,
        variable: tk.Variable,
        command: Callable[[], None] | None = None,
    ) -> None:
        """체크 표시가 있는 Flint 공용 메뉴 항목을 추가한다."""
        menu.add_checkbutton(
            label=label,
            variable=variable,
            command=command,
            indicatoron=True,
        )



# HEX 공용 메뉴/단축키 API (기존 flinters.menu에서 통합)
class MenuManager:
    """메뉴 표시와 단축키를 통합 관리한다. 실제 명령은 호출자가 제공한다."""

    def __init__(self, root, *, focus_widgets=()):
        self.root = root
        self.focus_widgets = tuple(focus_widgets)
        self._commands = {}
        self._sequences = {}
        self._popup = None

    @staticmethod
    def _normalize(key):
        parts = key.replace('<', '').replace('>', '').split('+')
        aliases = {'ctrl': 'Control', 'control': 'Control', 'shift': 'Shift',
                   'alt': 'Alt', 'return': 'Return', 'enter': 'Return',
                   'del': 'Delete', 'esc': 'Escape'}
        normalized = [aliases.get(part.lower(), part) for part in parts]
        modifiers = [x for x in ('Control', 'Alt', 'Shift') if x in normalized]
        keys = [x for x in normalized if x not in ('Control', 'Alt', 'Shift')]
        if len(keys) != 1:
            raise ValueError(f'잘못된 단축키: {key}')
        return '<' + '-'.join(modifiers + keys) + '>'

    def register(self, name, key, callback, *, scope='editor', bind=True):
        if name in self._commands:
            raise ValueError(f'중복 명령: {name}')
        sequence = self._normalize(key)
        if sequence in self._sequences:
            raise ValueError(f'단축키 충돌: {key} ({self._sequences[sequence]})')
        if scope not in ('editor', 'window'):
            raise ValueError(f'잘못된 단축키 범위: {scope}')
        self._commands[name] = (key, callback, scope)
        self._sequences[sequence] = name
        if bind:
            def invoke(event):
                if scope == 'editor' and event.widget not in self.focus_widgets:
                    return None
                callback()
                return 'break'
            self.root.bind_all(sequence, invoke)
        return sequence

    def invoke(self, name):
        self._commands[name][1]()
        return 'break'

    def label(self, name):
        return self._commands[name][0] if name in self._commands else ''

    def label_for(self, callback):
        for key, fn, _ in self._commands.values():
            if fn == callback:
                return key
        return ''

    def registered(self):
        return {name: key for name, (key, _, _) in self._commands.items()}

    def open(self, anchor, items, *, palette, checked=None):
        """테마형 팝업 메뉴. items는 (표시명, 콜백), (None, None)은 구분선."""
        self.close()
        c = palette()
        popup = tk.Toplevel(self.root)
        self._popup = popup
        popup.withdraw()
        popup.overrideredirect(True)
        popup.configure(bg=c['border'])
        panel = tk.Frame(popup, bg=c['panel'], padx=1, pady=1)
        panel.pack(fill='both', expand=True, padx=1, pady=1)
        for name, callback in items:
            if name is None:
                tk.Frame(panel, bg=c['border'], height=1).pack(fill='x', padx=4, pady=2)
                continue
            shown = checked(name) if checked else name
            row = tk.Frame(panel, bg=c['panel'], cursor='hand2')
            row.pack(fill='x')
            name_label = tk.Label(row, text=shown, font=('Malgun Gothic', 10),
                                  bg=c['panel'], fg=c['text'], anchor='w',
                                  padx=12, pady=5, cursor='hand2')
            name_label.pack(side='left')
            shortcut = self.label_for(callback)
            shortcut_label = None
            if shortcut:
                shortcut_label = tk.Label(row, text=shortcut, font=('Consolas', 9),
                                          bg=c['panel'], fg=c['sub'], anchor='e',
                                          padx=12, pady=5, cursor='hand2')
                shortcut_label.pack(side='right')
            parts = (row, name_label) + ((shortcut_label,) if shortcut_label else ())
            # 각 행의 위젯을 이벤트에 고정한다. 반복문 안의 hover 함수를
            # 람다가 늦게 참조하면 모든 행이 마지막 항목만 강조되는 문제가 생긴다.
            def hover(_event, color, widgets=parts):
                for widget in widgets:
                    widget.configure(bg=color)
            def invoke(_event, fn=callback):
                self.close()
                fn()
                return 'break'
            for widget in parts:
                widget.bind('<Enter>', lambda e, fn=hover: fn(e, palette()['hover']))
                widget.bind('<Leave>', lambda e, fn=hover: fn(e, palette()['panel']))
                widget.bind('<Button-1>', invoke)
        popup.update_idletasks()
        popup.geometry(f'+{anchor.winfo_rootx()}+{anchor.winfo_rooty()+anchor.winfo_height()}')
        popup.deiconify()
        popup.lift()
        popup.bind('<Escape>', lambda e: self.close())
        popup.bind('<FocusOut>', lambda e: popup.after(30, self.close))
        popup.focus_force()

    def close(self):
        popup = self._popup
        self._popup = None
        if popup is not None:
            try:
                popup.destroy()
            except tk.TclError:
                pass

# 프로그램에서 공통으로 선택해 사용하는 메뉴 항목과 기본 단축키.
# 콜백은 이 모듈에 두지 않고 각 프로그램에서 연결한다.
DEFAULT_MENUS = {
    'file': [('new', 'Ctrl+N'), ('open', 'Ctrl+O'), ('save', 'Ctrl+S'),
             ('save_as', 'Ctrl+Shift+S'), ('exit', None)],
    'edit': [('undo', 'Ctrl+Z'), ('redo', 'Ctrl+Y'), ('cut', 'Ctrl+X'),
             ('copy', 'Ctrl+C'), ('paste', 'Ctrl+V'), ('select_all', 'Ctrl+A'),
             ('delete', 'Delete')],
    'search': [('find', 'Ctrl+F'), ('find_next', 'F3'),
               ('replace', 'Ctrl+H'), ('goto', 'Ctrl+G')],
    'view': [('prev_page', 'Page Up'), ('next_page', 'Page Down'),
             ('file_start', 'Ctrl+Home'), ('file_end', 'Ctrl+End')],
    'settings': [],
}


def default_shortcut(command):
    """공용 메뉴 명령의 기본 단축키. 없으면 None."""
    for entries in DEFAULT_MENUS.values():
        for name, key in entries:
            if name == command:
                return key
    return None


def menu_items(group, commands, *, extras=(), omit=()):
    """기본 메뉴 중 제공된 (명령명: (표시명, 콜백))만 채택하고 전용 항목을 추가한다.

    extras: (표시명, 콜백) 또는 (None, None) 구분선의 순서 있는 목록.
    """
    excluded = set(omit)
    result = [commands[name] for name, _ in DEFAULT_MENUS[group]
              if name in commands and name not in excluded]
    result.extend(extras)
    return result


def build_menu_bar(root, groups, *, palette, opener):
    """Flint 테마형 메뉴바를 생성한다. groups: (메뉴명, 항목들)."""
    bar = tk.Frame(root, bg=palette()['bg'], height=26, bd=0)
    bar.pack(side='top', fill='x')
    bar.pack_propagate(False)
    labels = []
    for title, items in groups:
        label = tk.Label(bar, text=title, bg=palette()['bg'],
                         fg=palette()['text'], font=('Malgun Gothic', 10),
                         padx=8, cursor='hand2', bd=0)
        label.pack(side='left', fill='y')
        label.bind('<Button-1>', lambda e, w=label, data=items: opener(w, data))
        label.bind('<Enter>', lambda e, w=label: w.configure(bg=palette()['hover']))
        label.bind('<Leave>', lambda e, w=label: w.configure(bg=palette()['bg']))
        labels.append(label)
    return bar, labels
