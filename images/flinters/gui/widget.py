from __future__ import annotations
from pathlib import Path
import json
import re
import sys
import tkinter as tk
from tkinter import filedialog, simpledialog, font as tkfont, messagebox, ttk
from typing import Callable
from flinters.tooltip import ToolTip, TooltipManager

from .namecolor import FlintNameColorEditor

class FlintWidgetMixin:
    @staticmethod
    def info(title: str, message: str, *, parent=None) -> None:
        messagebox.showinfo(title, message, parent=parent)

    @staticmethod
    def warning(title: str, message: str, *, parent=None) -> None:
        messagebox.showwarning(title, message, parent=parent)

    @staticmethod
    def error(title: str, message: str, *, parent=None) -> None:
        messagebox.showerror(title, message, parent=parent)

    @staticmethod
    def ask_yes_no(title: str, message: str, *, parent=None) -> bool:
        return bool(messagebox.askyesno(title, message, parent=parent))

    @staticmethod
    def ask_ok_cancel(title: str, message: str, *, parent=None) -> bool:
        return bool(messagebox.askokcancel(title, message, parent=parent))

    @staticmethod
    def tooltip(
        widget: tk.Misc,
        text: str,
        *,
        delay: int | None = None,
        wraplength: int | None = None,
        ignore: bool = False,
    ) -> ToolTip:
        """호환용 래퍼. 실제 툴팁 동작은 flinters.tooltip에서 관리한다."""
        return TooltipManager.attach(
            widget,
            text,
            delay=delay,
            wraplength=wraplength,
            ignore=ignore,
        )

    @classmethod
    def button(
        cls,
        master,
        text: str,
        command: Callable | None = None,
        *,
        kind: str = "sea",
        compact: bool = False,
        large: bool = False,
        **kwargs,
    ) -> ttk.Button:
        """Flint 색상 체계와 버튼 크기 규격에 맞는 버튼을 생성한다."""
        style_map = {
            "emerald": "Emerald",
            "sea": "Sea",
            "danger": "Danger",
            "warning": "Warning",
            "muted": "Muted",
        }

        if compact and large:
            raise ValueError("compact와 large는 동시에 사용할 수 없습니다.")

        if kind == "primary":
            style_name = "Primary.TButton"
        else:
            if kind not in style_map:
                raise ValueError(f"알 수 없는 Flint 버튼 kind입니다: {kind!r}")
            prefix = style_map[kind]
            if compact:
                style_name = f"{prefix}.Compact.TButton"
            elif large:
                style_name = f"{prefix}.Large.TButton"
            else:
                style_name = f"{prefix}.TButton"

        return ttk.Button(master, text=text, command=command, style=style_name, **kwargs)

    @classmethod
    def add_button(
        cls,
        master,
        command: Callable | None = None,
        *,
        text: str = "+",
        **kwargs,
    ) -> ttk.Label:
        """박스 없이 기호만 보이는 Flint 공용 추가 컨트롤을 만든다.

        Button의 테마 최소폭을 쓰지 않아 기존 항목 바로 옆에 작게 붙일 수 있다.
        반환 객체는 ttk.Label이지만 ``state``/``configure(state=...)``로 비활성화할 수 있다.
        """
        widget = ttk.Label(
            master,
            text=text,
            style="AddSymbol.TLabel",
            cursor="hand2",
            takefocus=False,
            **kwargs,
        )

        def press(_event=None):
            if widget.instate(("disabled",)):
                return "break"
            widget.state(["pressed"])
            return "break"

        def release(_event=None):
            if widget.instate(("disabled",)):
                widget.state(["!pressed"])
                return "break"
            was_pressed = widget.instate(("pressed",))
            widget.state(["!pressed"])
            if was_pressed and command is not None:
                command()
            return "break"

        def enter(_event=None):
            if not widget.instate(("disabled",)):
                widget.state(["active"])

        def leave(_event=None):
            widget.state(["!active", "!pressed"])

        # Label 기반 + 컨트롤도 일반 버튼처럼 hover/pressed 상태를 직접 관리한다.
        # ttk.Label은 버튼처럼 active 상태가 항상 자동으로 잡히지 않으므로 명시적으로 연결한다.
        widget.bind("<Enter>", enter, add="+")
        widget.bind("<ButtonPress-1>", press, add="+")
        widget.bind("<ButtonRelease-1>", release, add="+")
        widget.bind("<Leave>", leave, add="+")
        return widget

    @classmethod
    def remove_button(
        cls,
        master,
        command: Callable | None = None,
        *,
        text: str = "×",
        **kwargs,
    ) -> tk.Label:
        """박스 없이 빨간 삭제 기호만 보이는 Flint 공용 제거 컨트롤을 만든다."""
        widget = tk.Label(
            master,
            text=text,
            font=(cls.FONT, 17, "bold"),
            foreground=cls.DANGER,
            # 삭제 기호는 주로 LabelFrame/패널 안에 놓이므로 주변 패널색과 이어지게 한다.
            # hover/pressed에서도 배경은 바꾸지 않고 × 글자색만 변화시킨다.
            background=cls.BACKGROUND,
            bd=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            cursor="hand2",
            takefocus=False,
            **kwargs,
        )

        def enter(_event=None):
            widget.configure(foreground=cls.DANGER_ACTIVE)

        def leave(_event=None):
            widget.configure(foreground=cls.DANGER)

        def press(_event=None):
            widget.configure(foreground=cls.DANGER_PRESSED)
            return "break"

        def release(_event=None):
            widget.configure(foreground=cls.DANGER_ACTIVE)
            if command is not None:
                command()
            return "break"

        widget.bind("<Enter>", enter, add="+")
        widget.bind("<Leave>", leave, add="+")
        widget.bind("<ButtonPress-1>", press, add="+")
        widget.bind("<ButtonRelease-1>", release, add="+")
        return widget

    @classmethod
    def selection_ring(
        cls,
        parent: tk.Misc,
        *,
        background: str,
        selected: bool = False,
        accent: str | None = None,
        thickness: int = 8,
        cursor: str = "hand2",
    ) -> tk.Frame:
        """테마에 영향받지 않는 실제 색상 선택 링 컨테이너를 만든다.

        ttk의 bordercolor는 OS 테마에 따라 무시될 수 있으므로 tk.Frame의 실제
        배경색을 링으로 사용한다. 링 두께만큼의 내부 여백도 이 공용 컨테이너가
        직접 확보하므로 안쪽 위젯은 선택 여부를 몰라도 되고 레이아웃도 흔들리지 않는다.
        """
        ring_color = accent if selected and accent else background
        edge = max(0, int(thickness))
        frame = tk.Frame(
            parent,
            background=ring_color,
            bd=0,
            highlightthickness=0,
            padx=edge,
            pady=edge,
            cursor=cursor,
        )
        setattr(frame, "_flint_ring_background", background)
        setattr(frame, "_flint_ring_accent", accent or cls.SASH)
        setattr(frame, "_flint_ring_thickness", edge)
        return frame

    @classmethod
    def bind_label_button_states(
        cls,
        label: ttk.Label,
        *,
        normal_style: Callable[[], str] | str,
        hover_ratio: float = 0.14,
        pressed_ratio: float = 0.22,
    ) -> None:
        """ttk.Label을 버튼처럼 hover/pressed 반응하게 만든다.

        이벤트마다 style을 갈아끼우지 않고 하나의 위젯 전용 스타일에
        active/pressed 상태 맵을 등록해 깜빡임 없이 처리한다.
        """
        style = ttk.Style(label)

        def resolve_style() -> str:
            return normal_style() if callable(normal_style) else str(normal_style)

        def rebuild_style() -> None:
            base_style = resolve_style()
            background = style.lookup(base_style, "background") or cls.TARGET
            foreground = style.lookup(base_style, "foreground") or "#ffffff"
            font = style.lookup(base_style, "font") or cls.BOLD_FONT
            anchor_value = style.lookup(base_style, "anchor") or "center"
            relief = style.lookup(base_style, "relief") or "flat"
            borderwidth = style.lookup(base_style, "borderwidth") or 0
            bordercolor = style.lookup(base_style, "bordercolor") or background

            hover_bg = cls._blend_hex(label, background, "#ffffff", hover_ratio)
            pressed_bg = cls._blend_hex(label, background, "#000000", pressed_ratio)
            hover_edge = cls._blend_hex(label, bordercolor, "#ffffff", hover_ratio * 0.65)
            pressed_edge = cls._blend_hex(label, bordercolor, "#000000", pressed_ratio * 0.55)

            widget_style = f"FlintLabelButton.{id(label)}.TLabel"
            style.configure(
                widget_style,
                background=background,
                foreground=foreground,
                font=font,
                anchor=anchor_value,
                relief=relief,
                borderwidth=borderwidth,
                bordercolor=bordercolor,
                lightcolor=bordercolor,
                darkcolor=bordercolor,
            )
            style.map(
                widget_style,
                background=[
                    ("pressed", pressed_bg),
                    ("active", hover_bg),
                    ("!disabled", background),
                ],
                bordercolor=[
                    ("pressed", pressed_edge),
                    ("active", hover_edge),
                    ("!disabled", bordercolor),
                ],
                lightcolor=[
                    ("pressed", pressed_edge),
                    ("active", hover_edge),
                    ("!disabled", bordercolor),
                ],
                darkcolor=[
                    ("pressed", pressed_edge),
                    ("active", hover_edge),
                    ("!disabled", bordercolor),
                ],
            )
            label.configure(style=widget_style)

        rebuild_style()

        def on_enter(_event=None):
            if not label.instate(("disabled",)):
                # 선택 상태가 외부에서 바뀌었을 수 있으므로 들어올 때 한 번만 갱신한다.
                rebuild_style()
                label.state(["active", "!pressed"])

        def on_leave(_event=None):
            label.state(["!active", "!pressed"])

        def on_press(_event=None):
            if not label.instate(("disabled",)):
                label.state(["pressed"])

        def on_release(_event=None):
            label.state(["!pressed"])
            if not label.instate(("disabled",)):
                label.state(["active"])

        label.bind("<Enter>", on_enter, add="+")
        label.bind("<Leave>", on_leave, add="+")
        label.bind("<ButtonPress-1>", on_press, add="+")
        label.bind("<ButtonRelease-1>", on_release, add="+")

    @staticmethod
    def _blend_hex(master: tk.Misc, start: str, end: str, ratio: float) -> str:
        """두 Tk 색상을 ratio(0~1)만큼 섞어 #RRGGBB로 반환한다."""
        ratio = max(0.0, min(float(ratio), 1.0))
        try:
            sr, sg, sb = master.winfo_rgb(start)
            er, eg, eb = master.winfo_rgb(end)
        except tk.TclError:
            return end

        sr, sg, sb = sr // 257, sg // 257, sb // 257
        er, eg, eb = er // 257, eg // 257, eb // 257
        r = round(sr + (er - sr) * ratio)
        g = round(sg + (eg - sg) * ratio)
        b = round(sb + (eb - sb) * ratio)
        return f"#{r:02x}{g:02x}{b:02x}"

    @classmethod
    def animate_label_selection(
        cls,
        label: ttk.Label,
        *,
        final_style: str,
        accent: str | None = None,
        duration_ms: int = 190,
        steps: int = 7,
    ) -> None:
        """Label 선택 시 짧은 눌림·하이라이트 후 최종 스타일에 안착시킨다."""
        try:
            if not label.winfo_exists():
                return
        except tk.TclError:
            return

        accent = accent or cls.SASH
        style = ttk.Style(label)
        base_style = str(label.cget("style") or "TLabel")
        background = (
            style.lookup(final_style, "background")
            or style.lookup(base_style, "background")
            or cls.PANEL
        )
        foreground = (
            style.lookup(final_style, "foreground")
            or style.lookup(base_style, "foreground")
            or cls.TEXT
        )
        font = style.lookup(final_style, "font") or cls.BOLD_FONT
        anchor_value = style.lookup(final_style, "anchor") or "center"
        temp_style = f"FlintSelectionPulse.{id(label)}.TLabel"

        steps = max(3, int(steps))
        interval = max(10, int(duration_ms) // steps)
        token = object()
        setattr(label, "_flint_selection_animation", token)

        def animate(index: int) -> None:
            try:
                if (
                    not label.winfo_exists()
                    or getattr(label, "_flint_selection_animation", None) is not token
                ):
                    return
            except tk.TclError:
                return

            if index >= steps:
                label.configure(style=final_style)
                return

            t = index / max(steps - 1, 1)
            if t < 0.30:
                press = 0.10 * (t / 0.30)
                glow = 0.20 * (t / 0.30)
            else:
                tail = (t - 0.30) / 0.70
                press = 0.10 * (1.0 - tail)
                glow = 0.20 + 0.80 * tail

            frame_bg = cls._blend_hex(label, background, "#000000", press)
            border = cls._blend_hex(label, background, accent, glow)

            style.configure(
                temp_style,
                background=frame_bg,
                foreground=foreground,
                font=font,
                anchor=anchor_value,
                relief="flat",
                borderwidth=2,
                bordercolor=border,
                lightcolor=border,
                darkcolor=border,
            )
            label.configure(style=temp_style)
            label.after(interval, lambda: animate(index + 1))

        animate(0)

    @classmethod
    def color_button(
        cls,
        master,
        text: str,
        color: str,
        command: Callable | None = None,
        *,
        style_name: str | None = None,
        **kwargs,
    ) -> ttk.Button:
        """임의 색상을 사용하는 Flint 공용 색상 버튼을 생성한다."""
        try:
            master.winfo_rgb(color)
        except tk.TclError as exc:
            raise ValueError(f"올바르지 않은 색상값입니다: {color!r}") from exc

        if style_name is None:
            cls._color_button_serial += 1
            style_name = f"FlintColor{cls._color_button_serial}.TButton"

        style = ttk.Style(master)
        foreground = FlintNameColorEditor.foreground_for(master, color) if "FlintNameColorEditor" in globals() else cls.ACCENT_TEXT
        style.configure(
            style_name,
            font=cls.BOLD_FONT,
            padding=(8, 4),
            foreground=foreground,
            background=color,
            relief="flat",
            borderwidth=0,
            bordercolor=color,
            lightcolor=color,
            darkcolor=color,
        )
        style.map(
            style_name,
            background=[("active", color), ("pressed", color)],
            foreground=[("!disabled", foreground)],
        )
        return ttk.Button(master, text=text, command=command, style=style_name, **kwargs)

    @staticmethod
    def bind_ellipsis(
        label: ttk.Label,
        source_var: tk.StringVar,
        display_var: tk.StringVar,
        *,
        transform: Callable[[str], str] | None = None,
        ellipsis: str = "...",
    ) -> None:
        """Label의 실제 표시 폭을 감시해 넘치는 텍스트만 말줄임한다.

        source_var에는 원문을 유지하고 display_var에는 화면에 들어가는 문자열만 넣는다.
        Label 크기와 원문이 바뀔 때마다 자동으로 다시 계산한다.
        """
        def update(_event=None) -> None:
            try:
                value = source_var.get()
                if transform is not None:
                    value = transform(value)

                label.update_idletasks()
                available = max(1, label.winfo_width())

                style = ttk.Style(label)
                style_name = label.cget("style") or "TLabel"
                font_spec = style.lookup(style_name, "font") or style.lookup("TLabel", "font")
                font = tkfont.Font(label, font=font_spec) if font_spec else tkfont.nametofont("TkDefaultFont")

                # ttk.Label의 실제 padding을 가능한 범위에서 제외한다.
                padding = label.cget("padding")
                if padding:
                    parts = label.tk.splitlist(padding)
                    nums = []
                    for part in parts:
                        try:
                            nums.append(int(float(part)))
                        except (TypeError, ValueError):
                            pass
                    if len(nums) == 1:
                        available -= nums[0] * 2
                    elif len(nums) >= 2:
                        available -= nums[0] * 2

                available = max(1, available)
                if font.measure(value) <= available:
                    display_var.set(value)
                    return

                usable = max(0, available - font.measure(ellipsis))
                lo, hi = 0, len(value)
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    if font.measure(value[:mid]) <= usable:
                        lo = mid
                    else:
                        hi = mid - 1
                display_var.set(value[:lo].rstrip() + ellipsis)
            except tk.TclError:
                return

        def schedule_update(_event=None) -> None:
            """즉시 계산한 뒤 idle 시점에 한 번 더 계산해 레이아웃 지연까지 잡는다."""
            update()
            try:
                label.after_idle(update)
            except tk.TclError:
                pass

        # Label 자체 폭이 변할 때와 원문이 바뀔 때 모두 즉시 감지한다.
        # 원문 변경 직후에는 부모 레이아웃이 아직 재계산 중일 수 있으므로
        # after_idle에서 실제 확정 폭을 기준으로 한 번 더 확인한다.
        label.bind("<Configure>", schedule_update, add="+")
        source_var.trace_add("write", lambda *_args: schedule_update())
        label.after_idle(update)

    @staticmethod
    def bind_wrapped_ellipsis(
        label: ttk.Label,
        source_var: tk.StringVar,
        display_var: tk.StringVar,
        *,
        max_lines: int = 2,
        ellipsis: str = "...",
    ) -> None:
        """고정 폭의 여러 줄 Label에서 마지막 보이는 줄 끝만 말줄임한다.

        원문은 source_var에 유지한다. 실제 Label 폭과 글꼴을 기준으로 줄 수를 계산해
        max_lines를 넘는 경우에만 마지막 줄 끝을 ... 처리한다.
        """
        max_lines = max(1, int(max_lines))

        def update(_event=None) -> None:
            try:
                value = source_var.get()
                label.update_idletasks()
                available = max(1, label.winfo_width())

                style = ttk.Style(label)
                style_name = label.cget("style") or "TLabel"
                font_spec = style.lookup(style_name, "font") or style.lookup("TLabel", "font")
                font = tkfont.Font(label, font=font_spec) if font_spec else tkfont.nametofont("TkDefaultFont")

                def fits(text: str) -> bool:
                    lines = 1
                    line_width = 0
                    for char in text:
                        if char == "\n":
                            lines += 1
                            line_width = 0
                            if lines > max_lines:
                                return False
                            continue

                        width = font.measure(char)
                        if line_width and line_width + width > available:
                            lines += 1
                            line_width = width
                            if lines > max_lines:
                                return False
                        else:
                            line_width += width
                    return True

                if fits(value):
                    display_var.set(value)
                    return

                lo, hi = 0, len(value)
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    candidate = value[:mid].rstrip() + ellipsis
                    if fits(candidate):
                        lo = mid
                    else:
                        hi = mid - 1
                display_var.set(value[:lo].rstrip() + ellipsis)
            except tk.TclError:
                return

        def schedule_update(_event=None) -> None:
            update()
            try:
                label.after_idle(update)
            except tk.TclError:
                pass

        label.bind("<Configure>", schedule_update, add="+")
        source_var.trace_add("write", lambda *_args: schedule_update())
        label.after_idle(update)

    @classmethod
    def fit_tree_columns(
        cls,
        tree: ttk.Treeview,
        *,
        fixed: tuple[str, ...] = (),
        expand: tuple[str, ...] = (),
        heading_padding: int = 24,
        expand_width: int = 420,
        expand_minwidth: int = 140,
    ) -> None:
        """고정 열은 제목 실제 폭에 맞추고, 확장 열은 남은 공간을 같은 비율로 사용한다."""
        style = ttk.Style(tree)
        heading_font = style.lookup("Treeview.Heading", "font") or "TkHeadingFont"

        for column in fixed:
            heading_text = tree.heading(column, "text")
            width = int(tree.tk.call("font", "measure", heading_font, heading_text)) + int(heading_padding)
            tree.column(column, width=width, minwidth=width, stretch=False)

        for column in expand:
            tree.column(
                column,
                width=int(expand_width),
                minwidth=int(expand_minwidth),
                stretch=True,
            )

    @classmethod
    def paned_window(
        cls,
        master,
        *,
        orient: str = "horizontal",
        **kwargs,
    ) -> ttk.Panedwindow:
        """빌더와 같은 Flint 공통 드래거를 만든다."""
        if orient not in {"horizontal", "vertical"}:
            raise ValueError("orient는 'horizontal' 또는 'vertical'이어야 합니다.")

        pane = ttk.Panedwindow(
            master,
            orient=orient,
            style="Workspace.TPanedwindow",
            **kwargs,
        )

        style = ttk.Style(pane)

        def _sash_hover(_event=None):
            style.configure(
                "Workspace.TPanedwindow",
                background=cls.SASH_HOVER,
                bordercolor=cls.SASH_HOVER,
                lightcolor=cls.SASH_HOVER,
                darkcolor=cls.SASH_HOVER,
            )

        def _sash_normal(_event=None):
            style.configure(
                "Workspace.TPanedwindow",
                background=cls.SASH,
                bordercolor=cls.SASH,
                lightcolor=cls.SASH,
                darkcolor=cls.SASH,
            )

        # Panedwindow 전체가 아니라 실제 sash 위에 포인터가 있을 때만 색을 바꾼다.
        # <Enter>는 pane 전체 영역에 들어오기만 해도 발생하므로 사용하지 않는다.
        hover_state = {"sash": False}

        def _track_sash(event):
            try:
                over_sash = pane.identify(event.x, event.y) != ""
            except tk.TclError:
                over_sash = False

            if over_sash != hover_state["sash"]:
                hover_state["sash"] = over_sash
                if over_sash:
                    _sash_hover()
                else:
                    _sash_normal()

        def _leave_pane(_event=None):
            hover_state["sash"] = False
            _sash_normal()

        pane.bind("<Motion>", _track_sash, add="+")
        pane.bind("<Leave>", _leave_pane, add="+")
        return pane

