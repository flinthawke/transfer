from __future__ import annotations
from pathlib import Path
import json
import re
import sys
import tkinter as tk
from tkinter import filedialog, simpledialog, font as tkfont, messagebox, ttk
from typing import Callable
from flinters.tooltip import ToolTip, TooltipManager

class FlintTheme:
    """Flint 도구의 공통 색상·폰트·ttk 스타일·GUI 도우미를 제공한다."""

    _checkbutton_images: dict[str, tk.PhotoImage] = {}
    _color_button_serial = 0

    # ======================================================================
    # [공용] 기본 디자인 토큰
    # 여러 Flint GUI가 함께 사용하는 폰트·색상·크기
    # ======================================================================

    # ------------------------------------------------------
    # Fonts
    # ------------------------------------------------------
    FONT = "Malgun Gothic"
    MONO_FONT = "Consolas"

    TITLE_FONT = (FONT, 19, "bold")
    SECTION_FONT = (FONT, 11, "bold")
    NORMAL_FONT = (FONT, 10)
    BOLD_FONT = (FONT, 10, "bold")
    SMALL_FONT = (FONT, 9)
    MONOSPACE_FONT = (MONO_FONT, 10)

    _checkbutton_images: dict[str, tk.PhotoImage] = {}
    _color_button_serial = 0
    FONT = "Malgun Gothic"
    MONO_FONT = "Consolas"
    TITLE_FONT = (FONT, 19, "bold")
    SECTION_FONT = (FONT, 11, "bold")
    NORMAL_FONT = (FONT, 10)
    BOLD_FONT = (FONT, 10, "bold")
    SMALL_FONT = (FONT, 9)
    MONOSPACE_FONT = (MONO_FONT, 10)
    EMERALD = "#22c58b"       # 일반 기능·선택·보조 작업
    EMERALD_ACTIVE = "#18ad79"
    EMERALD_PRESSED = "#129267"
    ADD = "#49b86e"
    ADD_ACTIVE = "#62cf83"
    ADD_PRESSED = "#2f8f51"
    SEA = "#19a8e5"           # 결정·승인·실행·생성
    SEA_ACTIVE = "#118fca"
    SEA_PRESSED = "#0d79ad"
    SILVER = "#f8fafb"          # 고휘도 은백색 · 보조 진행 상태·WhatsUp
    SILVER_PROGRESS = "#f8fafb" # 고휘도 화이트 실버 진행 막대
    SILVER_TROUGH = "#d9e1e5"   # 막대보다 살짝 어두운 은회색 바탕
    DANGER = "#c94b4b"        # 삭제·제거·위험 작업
    DANGER_ACTIVE = "#b83f3f"
    DANGER_PRESSED = "#9d3434"
    WARNING = "#d98c1e"       # 초기화·복원·주의 작업
    WARNING_ACTIVE = "#c87d14"
    WARNING_PRESSED = "#ad6910"
    MUTED = "#718096"         # 취소·닫기·비활성 성격
    MUTED_ACTIVE = "#5f6e82"
    MUTED_PRESSED = "#4d5b6d"
    MENU_SELECTED = "#0f83bd"
    MENU_SELECTED_ACTIVE = "#0c73a6"
    MENU_SELECTED_PRESSED = "#09618d"
    SASH = "#d4af37"           # 드래거 기본 색 - 황금색
    SASH_HOVER = "#c47f17"     # 드래거 마우스 오버 색 - 적색을 섞은 진한 황금색
    SASH_WIDTH = 4              # 드래거 두께
    DIVIDER = "#dce9f1"        # 일반 수평·세로 구분선
    BADAMAIL_DIVIDER = "#79c3e8"  # 바다메일 상·하단 핵심선 전용
    BACKGROUND = "#f5f9fc"
    PANEL = "#ffffff"
    FIELD = "#ffffff"
    FIELD_DISABLED = "#eef3f6"
    TEXT = "#17324d"
    SUBTEXT = "#6b7d8f"
    BORDER = "#d7e2e9"
    TOOLTIP = "#f8fbfd"
    TREE_HEADING = "#f1f7fa"
    TREE_HEADING_ACTIVE = "#e5f1f7"
    NOTEBOOK_TAB_ACTIVE = "#dff3fb"
    SCROLLBAR_THUMB = "#c7d5de"
    SCROLLBAR_ACTIVE = "#9fb4c2"
    SCROLLBAR_PRESSED = "#8aa3b3"
    SCROLLBAR_WIDTH = 12
    SCROLLBAR_ARROW_SIZE = 10
    PROGRESS_TROUGH = "#e7f0f5"
    PROGRESS_THICKNESS = 14
    TARGET = "#246f9e"
    THEME = "light"
    ACCENT_TEXT = "#ffffff"
    LIGHT_PALETTE = {
        "BACKGROUND": "#f5f9fc",
        "PANEL": "#ffffff",
        "FIELD": "#ffffff",
        "FIELD_DISABLED": "#eef3f6",
        "TEXT": "#17324d",
        "SUBTEXT": "#6b7d8f",
        "BORDER": "#d7e2e9",
        "TOOLTIP": "#f8fbfd",
        "TREE_HEADING": "#f1f7fa",
        "TREE_HEADING_ACTIVE": "#e5f1f7",
        "NOTEBOOK_TAB_ACTIVE": "#dff3fb",
        "SCROLLBAR_THUMB": "#c7d5de",
        "SCROLLBAR_ACTIVE": "#9fb4c2",
        "SCROLLBAR_PRESSED": "#8aa3b3",
        "PROGRESS_TROUGH": "#e7f0f5",
        "DIVIDER": "#dce9f1",
        "SILVER": "#f8fafb",
        "SILVER_PROGRESS": "#f8fafb",
        "SILVER_TROUGH": "#d9e1e5",
        "TARGET": "#246f9e",
        "MUTED": "#718096",
        "MUTED_ACTIVE": "#5f6e82",
        "MUTED_PRESSED": "#4d5b6d",
        "ACCENT_TEXT": "#ffffff",
    }
    DARK_PALETTE = {
        "BACKGROUND": "#111820",
        "PANEL": "#18222c",
        "FIELD": "#202c37",
        "FIELD_DISABLED": "#293540",
        "TEXT": "#e8f0f5",
        "SUBTEXT": "#9aabba",
        "BORDER": "#344452",
        "TOOLTIP": "#26333e",
        "TREE_HEADING": "#22303b",
        "TREE_HEADING_ACTIVE": "#2b3b47",
        "NOTEBOOK_TAB_ACTIVE": "#263f4d",
        "SCROLLBAR_THUMB": "#4c5e6b",
        "SCROLLBAR_ACTIVE": "#607583",
        "SCROLLBAR_PRESSED": "#718894",
        "PROGRESS_TROUGH": "#26343f",
        "DIVIDER": "#30424f",
        "SILVER": "#dce6ec",
        "SILVER_PROGRESS": "#dce6ec",
        "SILVER_TROUGH": "#3b4b57",
        "TARGET": "#287eab",
        "MUTED": "#596a78",
        "MUTED_ACTIVE": "#687d8d",
        "MUTED_PRESSED": "#475763",
        "ACCENT_TEXT": "#ffffff",
    }

    @classmethod
    def set_language_font(cls, language: str) -> None:
        """표시 언어에 맞춰 Flint 공용 UI 글꼴을 선택한다."""
        code = str(language).strip().lower()
        cls.FONT = "Malgun Gothic" if code.startswith("ko") else "Segoe UI"
        cls.TITLE_FONT = (cls.FONT, 19, "bold")
        cls.SECTION_FONT = (cls.FONT, 11, "bold")
        cls.NORMAL_FONT = (cls.FONT, 10)
        cls.BOLD_FONT = (cls.FONT, 10, "bold")
        cls.SMALL_FONT = (cls.FONT, 9)

    @classmethod
    def set_theme(cls, theme: str) -> None:
        """Flint 전체 GUI 팔레트를 light/dark 중 하나로 전환한다."""
        theme = str(theme).strip().lower()
        if theme not in {"light", "dark"}:
            raise ValueError(f"지원하지 않는 Flint 테마입니다: {theme!r}")

        palette = cls.DARK_PALETTE if theme == "dark" else cls.LIGHT_PALETTE
        for name, value in palette.items():
            setattr(cls, name, value)
        cls.THEME = theme

    @classmethod
    def is_dark(cls) -> bool:
        return cls.THEME == "dark"

    @classmethod
    def _refresh_tk_palette(cls, master: tk.Misc) -> None:
        """이미 생성된 기본 Tk 위젯 중 Flint 팔레트 색만 현재 테마로 갱신한다."""
        light = cls.LIGHT_PALETTE
        dark = cls.DARK_PALETTE

        def is_palette_color(widget: tk.Misc, value: str, token: str) -> bool:
            try:
                rgb = widget.winfo_rgb(value)
                return rgb in {
                    widget.winfo_rgb(light[token]),
                    widget.winfo_rgb(dark[token]),
                }
            except (tk.TclError, KeyError):
                return False

        def update(widget: tk.Misc) -> None:
            try:
                config: dict[str, str] = {}

                if isinstance(widget, (tk.Text, tk.Listbox)):
                    if is_palette_color(widget, str(widget.cget("background")), "FIELD"):
                        config["background"] = cls.FIELD
                    if is_palette_color(widget, str(widget.cget("foreground")), "TEXT"):
                        config["foreground"] = cls.TEXT
                    if is_palette_color(widget, str(widget.cget("selectbackground")), "SEA"):
                        config["selectbackground"] = cls.SEA
                    if is_palette_color(widget, str(widget.cget("selectforeground")), "ACCENT_TEXT"):
                        config["selectforeground"] = cls.ACCENT_TEXT
                    if isinstance(widget, tk.Text) and is_palette_color(
                        widget, str(widget.cget("insertbackground")), "TEXT"
                    ):
                        config["insertbackground"] = cls.TEXT

                elif isinstance(widget, tk.Canvas):
                    if is_palette_color(widget, str(widget.cget("background")), "BACKGROUND"):
                        config["background"] = cls.BACKGROUND
                    elif is_palette_color(widget, str(widget.cget("background")), "FIELD"):
                        config["background"] = cls.FIELD

                elif isinstance(widget, (tk.Frame, tk.Label)):
                    if is_palette_color(widget, str(widget.cget("background")), "BACKGROUND"):
                        config["background"] = cls.BACKGROUND
                    elif is_palette_color(widget, str(widget.cget("background")), "FIELD"):
                        config["background"] = cls.FIELD
                    elif is_palette_color(widget, str(widget.cget("background")), "PANEL"):
                        config["background"] = cls.PANEL
                    if isinstance(widget, tk.Label) and is_palette_color(
                        widget, str(widget.cget("foreground")), "TEXT"
                    ):
                        config["foreground"] = cls.TEXT

                if config:
                    widget.configure(**config)

                for child in widget.winfo_children():
                    update(child)
            except tk.TclError:
                return

        update(master)

    @classmethod
    def apply(cls, master=None) -> ttk.Style:
        """현재 Tk 인스턴스에 Flint 공통 스타일을 등록하고 Style을 반환한다."""
        style = ttk.Style(master)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        if master is not None:
            try:
                master.configure(background=cls.BACKGROUND)
                master.option_add("*Listbox.background", cls.FIELD)
                master.option_add("*Listbox.foreground", cls.TEXT)
                master.option_add("*Listbox.selectBackground", cls.SEA)
                master.option_add("*Listbox.selectForeground", cls.ACCENT_TEXT)
                master.option_add("*Listbox.highlightBackground", cls.BORDER)
                master.option_add("*Listbox.highlightColor", cls.SEA)
                master.option_add("*Text.background", cls.FIELD)
                master.option_add("*Text.foreground", cls.TEXT)
                master.option_add("*Text.insertBackground", cls.TEXT)
                master.option_add("*Text.selectBackground", cls.SEA)
                master.option_add("*Text.selectForeground", cls.ACCENT_TEXT)
                master.option_add("*Canvas.background", cls.BACKGROUND)
            except tk.TclError:
                pass

            # option_add()는 이후 생성되는 기본 Tk 위젯에만 적용된다.
            # 이미 만들어진 Text/Listbox/Canvas/Frame/Label도 Flint 팔레트 색을
            # 사용 중인 경우에만 현재 테마 색으로 다시 맞춘다.
            # 프로그램이 별도로 지정한 콘솔·특수 색상은 건드리지 않는다.
            cls._refresh_tk_palette(master)

        style.configure(".", font=cls.NORMAL_FONT)
        style.configure("TFrame", background=cls.BACKGROUND)
        style.configure("TLabel", background=cls.BACKGROUND, foreground=cls.TEXT)
        style.configure("TCheckbutton", background=cls.BACKGROUND, foreground=cls.TEXT)
        style.map(
            "TCheckbutton",
            background=[
                ("disabled", cls.BACKGROUND),
                ("active", cls.BACKGROUND),
                ("!disabled", cls.BACKGROUND),
            ],
            foreground=[
                ("disabled", cls.SUBTEXT),
                ("!disabled", cls.TEXT),
            ],
        )
        style.configure("TRadiobutton", background=cls.BACKGROUND, foreground=cls.TEXT)
        cls._configure_checkbutton_indicator(style, master)

        # ==================================================================
        # [공용] 메뉴 계열 컴팩트 스타일
        # 현재 일부 Flint 도구에서만 사용하더라도 GUI 성격의 공통 규격으로 관리한다.
        # ==================================================================

        # 메뉴 연결 영역에서 쓰는 컴팩트 버튼.
        # 기본 Menu.TButton 크기는 유지하고 필요한 화면에서만 밀도를 높여 사용한다.
        style.configure(
            "CompactMenu.TButton",
            font=cls.SMALL_FONT,
            padding=(8, 3),
            foreground=cls.ACCENT_TEXT,
            background=cls.EMERALD,
            relief="flat",
            borderwidth=0,
            bordercolor=cls.EMERALD,
            lightcolor=cls.EMERALD,
            darkcolor=cls.EMERALD,        )
        style.map(
            "CompactMenu.TButton",
            background=[("active", cls.EMERALD_ACTIVE), ("pressed", cls.EMERALD_PRESSED)],
            foreground=[("disabled", "#d8eee9"), ("!disabled", cls.ACCENT_TEXT)],
        )

        style.configure(
            "CompactSelectedMenu.TButton",
            font=cls.SMALL_FONT,
            padding=(8, 3),
            foreground=cls.ACCENT_TEXT,
            background=cls.MENU_SELECTED,
            relief="flat",
            borderwidth=0,
            bordercolor=cls.MENU_SELECTED,
            lightcolor=cls.MENU_SELECTED,
            darkcolor=cls.MENU_SELECTED,        )
        style.map(
            "CompactSelectedMenu.TButton",
            background=[("active", cls.MENU_SELECTED_ACTIVE), ("pressed", cls.MENU_SELECTED_PRESSED)],
            foreground=[("disabled", "#d8eee9"), ("!disabled", cls.ACCENT_TEXT)],
        )

        # 하위 메뉴 펼침/접힘 버튼은 Flint의 Sea 계열로 작게 구분한다.
        style.configure(
            "MenuToggle.TButton",
            font=cls.SMALL_FONT,
            padding=(4, 3),
            foreground=cls.ACCENT_TEXT,
            background=cls.SEA,
            relief="flat",
            borderwidth=0,
            bordercolor=cls.SEA,
            lightcolor=cls.SEA,
            darkcolor=cls.SEA,        )
        style.map(
            "MenuToggle.TButton",
            background=[("active", cls.SEA_ACTIVE), ("pressed", cls.SEA_PRESSED)],
            foreground=[("disabled", "#d8e8f2"), ("!disabled", cls.ACCENT_TEXT)],
        )

        # ==================================================================
        # [공용] ttk 위젯 스타일
        # ==================================================================

        style.configure(
            "TEntry",
            padding=(8, 5),
            fieldbackground=cls.FIELD,
            background=cls.FIELD,
            foreground=cls.TEXT,
            insertcolor=cls.TEXT,
            bordercolor=cls.BORDER,
            lightcolor=cls.BORDER,
            darkcolor=cls.BORDER,
        )
        style.map(
            "TEntry",
            fieldbackground=[
                ("disabled", cls.FIELD_DISABLED),
                ("readonly", cls.FIELD),
                ("!disabled", cls.FIELD),
            ],
            foreground=[
                ("disabled", cls.SUBTEXT),
                ("!disabled", cls.TEXT),
            ],
        )

        style.configure(
            "TCombobox",
            padding=(7, 4),
            fieldbackground=cls.FIELD,
            background=cls.FIELD,
            foreground=cls.TEXT,
            arrowcolor=cls.SUBTEXT,
            bordercolor=cls.BORDER,
            lightcolor=cls.BORDER,
            darkcolor=cls.BORDER,
        )
        style.map(
            "TCombobox",
            fieldbackground=[
                ("disabled", cls.FIELD_DISABLED),
                ("readonly", cls.FIELD),
                ("!disabled", cls.FIELD),
            ],
            background=[
                ("disabled", cls.FIELD_DISABLED),
                ("readonly", cls.FIELD),
                ("!disabled", cls.FIELD),
            ],
            foreground=[
                ("disabled", cls.SUBTEXT),
                ("readonly", cls.TEXT),
                ("!disabled", cls.TEXT),
            ],
            selectbackground=[("readonly", cls.FIELD)],
            selectforeground=[("readonly", cls.TEXT)],
        )

        style.configure(
            "TLabelframe",
            background=cls.BACKGROUND,
            borderwidth=1,
            relief="solid",
            bordercolor=cls.BORDER,
            lightcolor=cls.BORDER,
            darkcolor=cls.BORDER,
        )
        style.configure(
            "TLabelframe.Label",
            background=cls.BACKGROUND,
            foreground=cls.TEXT,
        )

        style.configure("Title.TLabel", font=cls.TITLE_FONT, foreground=cls.TEXT)
        style.configure("Section.TLabel", font=cls.SECTION_FONT, foreground=cls.TEXT)
        style.configure("Subtle.TLabel", foreground=cls.SUBTEXT)
        style.configure("Primary.TButton", font=cls.NORMAL_FONT, padding=(9, 3))
        style.configure("Compact.TButton", font=cls.SMALL_FONT, padding=(6, 1))
        style.configure("Large.TButton", font=cls.BOLD_FONT, padding=(10, 6))

        # 박스 없이 기호 자체만 보이는 공용 추가 컨트롤.
        # ttk.Button의 테마 최소폭을 피하려고 Label 기반으로 만든다.
        style.configure(
            "AddSymbol.TLabel",
            font=(cls.FONT, 17, "bold"),
            # + 기호는 글꼴 자체의 시각 중심이 아래쪽에 있어 조금 더 위로 보정한다.
            # 아래 여백을 늘려 기호의 시각적 중심을 주변 설정 버튼과 맞춘다.
            padding=(0, 0, 0, 7),
            foreground=cls.ADD,
            background=cls.BACKGROUND,
            anchor="center",
        )
        style.map(
            "AddSymbol.TLabel",
            foreground=[
                ("disabled", cls.BORDER),
                ("pressed", cls.ADD_PRESSED),
                ("active", cls.ADD_ACTIVE),
                ("!disabled", cls.ADD),
            ],
            background=[
                ("disabled", cls.BACKGROUND),
                ("pressed", cls.BACKGROUND),
                ("active", cls.BACKGROUND),
                ("!disabled", cls.BACKGROUND),
            ],
        )

        # 버튼 규격: 기본 / Compact / Large. 기본 크기는 별도 이름을 붙이지 않는다.
        button_styles = (
            ("Emerald", cls.EMERALD, cls.EMERALD_ACTIVE, cls.EMERALD_PRESSED, "#d8eee9"),
            ("Sea", cls.SEA, cls.SEA_ACTIVE, cls.SEA_PRESSED, "#dcecf5"),
            ("Danger", cls.DANGER, cls.DANGER_ACTIVE, cls.DANGER_PRESSED, "#f2dede"),
            ("Warning", cls.WARNING, cls.WARNING_ACTIVE, cls.WARNING_PRESSED, "#f7ead1"),
            ("Muted", cls.MUTED, cls.MUTED_ACTIVE, cls.MUTED_PRESSED, "#e3e7e9"),
        )

        for prefix, normal, active, pressed, disabled_fg in button_styles:
            cls._button(
                style,
                f"{prefix}.TButton",
                normal,
                active,
                pressed,
                disabled_fg,
                font=cls.NORMAL_FONT,
                padding=(9, 3),
            )
            cls._button(
                style,
                f"{prefix}.Compact.TButton",
                normal,
                active,
                pressed,
                disabled_fg,
                font=cls.SMALL_FONT,
                padding=(6, 1),
            )
            cls._button(
                style,
                f"{prefix}.Large.TButton",
                normal,
                active,
                pressed,
                disabled_fg,
                font=cls.BOLD_FONT,
                padding=(10, 6),
            )

        style.configure(
            "Menu.TButton",
            font=cls.NORMAL_FONT,
            padding=(12, 8),
            foreground=cls.ACCENT_TEXT,
            background=cls.EMERALD,
            relief="flat",
            borderwidth=0,
            bordercolor=cls.EMERALD,
            lightcolor=cls.EMERALD,
            darkcolor=cls.EMERALD,        )
        style.map(
            "Menu.TButton",
            background=[("active", cls.EMERALD_ACTIVE), ("pressed", cls.EMERALD_PRESSED)],
            foreground=[("disabled", "#d8eee9"), ("!disabled", cls.ACCENT_TEXT)],
        )

        style.configure(
            "SelectedMenu.TButton",
            font=cls.BOLD_FONT,
            padding=(12, 8),
            foreground=cls.ACCENT_TEXT,
            background=cls.MENU_SELECTED,
            relief="flat",
            borderwidth=0,
            bordercolor=cls.MENU_SELECTED,
            lightcolor=cls.MENU_SELECTED,
            darkcolor=cls.MENU_SELECTED,        )
        style.map(
            "SelectedMenu.TButton",
            background=[("active", cls.MENU_SELECTED_ACTIVE), ("pressed", cls.MENU_SELECTED_PRESSED)],
            foreground=[("disabled", "#d8eee9"), ("!disabled", cls.ACCENT_TEXT)],
        )

        # ttk.Panedwindow의 실제 드래거 두께는 clam 테마의 Sash 요소가 결정한다.
        # sashwidth는 ttk에서 테마에 따라 무시될 수 있으므로 Sash.sashthickness를 직접 지정한다.
        style.configure(
            "Sash",
            sashthickness=cls.SASH_WIDTH,
            gripcount=0,
        )
        style.configure(
            "Workspace.TPanedwindow",
            background=cls.SASH,
            sashrelief="flat",
            borderwidth=0,
            bordercolor=cls.SASH,
            lightcolor=cls.SASH,
            darkcolor=cls.SASH,
        )

        style.configure(
            "Target.TLabel",
            background=cls.TARGET,
            foreground=cls.ACCENT_TEXT,
            anchor="center",
            font=cls.BOLD_FONT,
        )
        style.configure(
            "Dest.TLabel",
            background=cls.EMERALD,
            foreground=cls.ACCENT_TEXT,
            anchor="center",
            font=cls.BOLD_FONT,
        )
        style.configure(
            "Slot.TFrame",
            background=cls.BACKGROUND,
            relief="solid",
            borderwidth=1,
            bordercolor=cls.BORDER,
            lightcolor=cls.BORDER,
            darkcolor=cls.BORDER,
        )
        style.configure(
            "Panel.TFrame",
            background=cls.BACKGROUND,
            relief="solid",
            borderwidth=1,
            bordercolor=cls.BORDER,
            lightcolor=cls.BORDER,
            darkcolor=cls.BORDER,
        )

        # [공용] 선택 상태 표현
        # 어떤 항목이 선택되었는지는 각 프로그램이 판단하고
        # 선택된 슬롯/번호/대상 칸을 어떻게 보일지는 GUI 공용 스타일이 맡는다.
        style.configure(
            "SelectedSlot.TFrame",
            background=cls.BACKGROUND,
            relief="solid",
            borderwidth=2,
            bordercolor=cls.SASH,
            lightcolor=cls.SASH,
            darkcolor=cls.SASH,
        )
        style.configure(
            "SelectedSlotNumber.TLabel",
            background=cls.NOTEBOOK_TAB_ACTIVE,
            foreground=cls.TEXT,
            anchor="center",
            font=cls.BOLD_FONT,
            relief="solid",
            borderwidth=1,
            bordercolor=cls.SASH,
            lightcolor=cls.SASH,
            darkcolor=cls.SASH,
        )
        style.configure(
            "SelectedSource.Target.TLabel",
            background=cls.TARGET,
            foreground=cls.ACCENT_TEXT,
            anchor="center",
            font=cls.BOLD_FONT,
            relief="solid",
            borderwidth=2,
            bordercolor=cls.SASH,
            lightcolor=cls.SASH,
            darkcolor=cls.SASH,
        )
        style.configure(
            "SelectedDestination.Dest.TLabel",
            background=cls.EMERALD,
            foreground=cls.ACCENT_TEXT,
            anchor="center",
            font=cls.BOLD_FONT,
            relief="solid",
            borderwidth=2,
            bordercolor=cls.SASH,
            lightcolor=cls.SASH,
            darkcolor=cls.SASH,
        )

        style.configure(
            "Treeview",
            font=cls.NORMAL_FONT,
            rowheight=29,
            background=cls.FIELD,
            fieldbackground=cls.FIELD,
            foreground=cls.TEXT,
            bordercolor=cls.BORDER,
            lightcolor=cls.BORDER,
            darkcolor=cls.BORDER,
        )
        style.configure(
            "Treeview.Heading",
            font=cls.BOLD_FONT,
            padding=(6, 5),
            background=cls.TREE_HEADING,
            foreground=cls.TEXT,
        )
        style.map(
            "Treeview",
            background=[("selected", cls.SEA)],
            foreground=[("selected", cls.ACCENT_TEXT)],
        )
        style.map(
            "Treeview.Heading",
            background=[("active", cls.TREE_HEADING_ACTIVE)],
        )

        # FlintFileList 전용: 일반 Treeview와 같은 담백한 헤더를 사용하되
        # 행/헤더의 세로 여백만 조금 줄인다.
        # 헤더 테두리는 유지해서 "상태 | 파일" 열 구분선이 보이게 한다.
        style.configure(
            "FlintFileList.Treeview",
            font=cls.NORMAL_FONT,
            rowheight=27,
            background=cls.FIELD,
            fieldbackground=cls.FIELD,
            foreground=cls.TEXT,
        )
        style.map(
            "FlintFileList.Treeview",
            background=[("selected", cls.SEA)],
            foreground=[("selected", cls.ACCENT_TEXT)],
        )
        style.configure(
            "FlintFileList.Treeview.Heading",
            font=cls.BOLD_FONT,
            padding=(6, 4),
            background=cls.TREE_HEADING,
            foreground=cls.TEXT,
            borderwidth=1,
            relief="solid",
            bordercolor=cls.BORDER,
        )
        style.map(
            "FlintFileList.Treeview.Heading",
            background=[("active", cls.TREE_HEADING_ACTIVE)],
            foreground=[("!disabled", cls.TEXT)],
        )

        style.configure("TNotebook", background=cls.BACKGROUND, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            font=cls.NORMAL_FONT,
            padding=(12, 7),
            background=cls.PANEL,
            foreground=cls.TEXT,
        )
        style.map(
            "TNotebook.Tab",
            background=[
                ("selected", cls.FIELD),
                ("active", cls.NOTEBOOK_TAB_ACTIVE),
                ("!selected", cls.PANEL),
            ],
            foreground=[
                ("selected", cls.TEXT),
                ("active", cls.TEXT),
                ("!selected", cls.TEXT),
            ],
        )

        # 기본 Tk 스크롤바처럼 장식을 줄인 담백한 ttk 스크롤바
        for scrollbar_style in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            style.configure(
                scrollbar_style,
                gripcount=0,
                width=cls.SCROLLBAR_WIDTH,
                arrowsize=cls.SCROLLBAR_ARROW_SIZE,
                borderwidth=0,
                relief="flat",
                background=cls.SCROLLBAR_THUMB,
                troughcolor=cls.FIELD,
                bordercolor=cls.FIELD,
                lightcolor=cls.SCROLLBAR_THUMB,
                darkcolor=cls.SCROLLBAR_THUMB,
                arrowcolor=cls.SUBTEXT,
            )
            style.map(
                scrollbar_style,
                background=[
                    ("pressed", cls.SCROLLBAR_PRESSED),
                    ("active", cls.SCROLLBAR_ACTIVE),
                    ("!disabled", cls.SCROLLBAR_THUMB),
                ],
                lightcolor=[
                    ("pressed", cls.SCROLLBAR_PRESSED),
                    ("active", cls.SCROLLBAR_ACTIVE),
                    ("!disabled", cls.SCROLLBAR_THUMB),
                ],
                darkcolor=[
                    ("pressed", cls.SCROLLBAR_PRESSED),
                    ("active", cls.SCROLLBAR_ACTIVE),
                    ("!disabled", cls.SCROLLBAR_THUMB),
                ],
            )

        style.configure(
            "Emerald.Horizontal.TProgressbar",
            background=cls.EMERALD,
            troughcolor=cls.PROGRESS_TROUGH,
            bordercolor=cls.BORDER,
            lightcolor=cls.EMERALD,
            darkcolor=cls.EMERALD,
            thickness=cls.PROGRESS_THICKNESS,
        )
        style.configure(
            "Sea.Horizontal.TProgressbar",
            background=cls.SEA,
            troughcolor=cls.PROGRESS_TROUGH,
            bordercolor=cls.BORDER,
            lightcolor=cls.SEA,
            darkcolor=cls.SEA,
            thickness=cls.PROGRESS_THICKNESS,
        )
        style.configure(
            "Silver.Horizontal.TProgressbar",
            background=cls.SILVER_PROGRESS,
            troughcolor=cls.SILVER_TROUGH,
            bordercolor=cls.SILVER_PROGRESS,
            lightcolor=cls.SILVER_PROGRESS,
            darkcolor=cls.SILVER_PROGRESS,
            thickness=cls.PROGRESS_THICKNESS,
        )

        return style

    @classmethod
    def _configure_checkbutton_indicator(
        cls,
        style: ttk.Style,
        master=None,
    ) -> None:
        """clam 테마에서도 체크 상태를 X가 아닌 ✓로 표시한다."""
        if master is None:
            master = style.master

        def make_indicator(
            *,
            checked: bool,
            disabled: bool = False,
        ) -> tk.PhotoImage:
            image = tk.PhotoImage(master=master, width=16, height=16)
            fill = cls.BACKGROUND if disabled else cls.FIELD
            border = cls.SUBTEXT if disabled else cls.BORDER
            check = cls.SUBTEXT if disabled else cls.EMERALD_PRESSED

            image.put(fill, to=(1, 1, 15, 15))
            image.put(border, to=(1, 1, 15, 2))
            image.put(border, to=(1, 14, 15, 15))
            image.put(border, to=(1, 1, 2, 15))
            image.put(border, to=(14, 1, 15, 15))

            if checked:
                # 2px 두께의 또렷한 체크 표시
                points = (
                    (4, 8), (5, 9), (6, 10), (7, 11),
                    (7, 10), (8, 9), (9, 8), (10, 7), (11, 6), (12, 5),
                )
                for x, y in points:
                    image.put(check, to=(x, y, x + 2, y + 2))

            return image

        # ttk의 사용자 정의 element는 한 번 생성되면 같은 이름으로 이미지를 교체할 수 없다.
        # 따라서 같은 테마로 다시 돌아왔을 때는 새 PhotoImage를 만들지 않고 기존 element와
        # 그 element가 참조하는 이미지를 그대로 재사용한다. 새 이미지를 같은 보관 키에
        # 덮어쓰면 기존 PhotoImage가 해제되어 체크 표시 자체가 사라질 수 있다.
        element_name = f"flinters.{cls.THEME}.Checkbutton.indicator"
        if element_name not in style.element_names():
            images = {
                "off": make_indicator(checked=False),
                "on": make_indicator(checked=True),
                "off_disabled": make_indicator(checked=False, disabled=True),
                "on_disabled": make_indicator(checked=True, disabled=True),
            }
            key_prefix = f"{master}:{cls.THEME}"
            cls._checkbutton_images.update(
                {f"{key_prefix}:{name}": image for name, image in images.items()}
            )
            style.element_create(
                element_name,
                "image",
                images["off"],
                ("disabled", "selected", images["on_disabled"]),
                ("disabled", images["off_disabled"]),
                ("selected", images["on"]),
                border=0,
                sticky="",
            )

        style.layout(
            "TCheckbutton",
            [
                (
                    "Checkbutton.padding",
                    {
                        "sticky": "nswe",
                        "children": [
                            (element_name, {"side": "left", "sticky": ""}),
                            (
                                "Checkbutton.focus",
                                {
                                    "side": "left",
                                    "sticky": "w",
                                    "children": [
                                        ("Checkbutton.label", {"sticky": "nswe"})
                                    ],
                                },
                            ),
                        ],
                    },
                )
            ],
        )

    @classmethod
    def _button(
        cls,
        style: ttk.Style,
        name: str,
        normal: str,
        active: str,
        pressed: str,
        disabled_foreground: str,
        *,
        font=None,
        padding=None,
    ) -> None:
        style.configure(
            name,
            font=font or cls.BOLD_FONT,
            padding=padding or (10, 6),
            foreground=cls.ACCENT_TEXT,
            background=normal,
            relief="flat",
            borderwidth=0,
            bordercolor=normal,
            lightcolor=normal,
            darkcolor=normal,
        )
        style.map(
            name,
            background=[("active", active), ("pressed", pressed)],
            foreground=[("disabled", disabled_foreground), ("!disabled", cls.ACCENT_TEXT)],
        )

