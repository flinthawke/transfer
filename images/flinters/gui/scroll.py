from __future__ import annotations
from pathlib import Path
import json
import re
import sys
import tkinter as tk
from tkinter import filedialog, simpledialog, font as tkfont, messagebox, ttk
from typing import Callable
from flinters.tooltip import ToolTip, TooltipManager

class FlintScrollMixin:
    @staticmethod
    def bind_mousewheel(canvas: tk.Canvas, widget: tk.Misc | None = None) -> None:
        """같은 스크롤 영역 안에서는 어느 위젯 위에서도 마우스 휠이 동작하게 한다.

        ``widget``은 휠이 유효한 화면 영역이다. Canvas의 create_window()로 들어간
        자식 위젯은 Tk 위젯 계층만으로 판정하면 놓칠 수 있으므로, 현재 마우스 포인터가
        지정 영역의 실제 화면 사각형 안에 있는지를 기준으로 처리한다.
        """
        target = widget or canvas
        root = target.winfo_toplevel()

        def pointer_is_inside_target() -> bool:
            try:
                if not target.winfo_exists() or not target.winfo_ismapped():
                    return False

                px = target.winfo_pointerx()
                py = target.winfo_pointery()
                left = target.winfo_rootx()
                top = target.winfo_rooty()
                right = left + target.winfo_width()
                bottom = top + target.winfo_height()

                return left <= px < right and top <= py < bottom
            except tk.TclError:
                return False

        def on_mousewheel(event):
            # bind_all()은 같은 Tk 애플리케이션의 다른 Toplevel 창에도 전달된다.
            # 현재 휠 이벤트가 발생한 창과 이 Canvas가 속한 창이 다르면 무시해서
            # 뒤에 가려진 다른 창의 스크롤 영역이 휠을 가로채지 않게 한다.
            try:
                event_widget = getattr(event, "widget", None)
                if event_widget is None or event_widget.winfo_toplevel() is not root:
                    return None
            except (tk.TclError, AttributeError):
                return None

            if not pointer_is_inside_target():
                return None

            if getattr(event, "num", None) == 4:
                canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                canvas.yview_scroll(1, "units")
            elif getattr(event, "delta", 0):
                canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
            else:
                return None
            return "break"

        root.bind_all("<MouseWheel>", on_mousewheel, add="+")
        root.bind_all("<Button-4>", on_mousewheel, add="+")
        root.bind_all("<Button-5>", on_mousewheel, add="+")

    @staticmethod
    def bind_local_mousewheel(widget: tk.Misc, fallback: tk.Misc | None = None) -> None:
        """포커스 상태에 따라 로컬 위젯 또는 바깥 스크롤 영역만 움직인다.

        Text처럼 자체 yview_scroll()을 가진 위젯에 사용한다. 클릭해서 포커스가 있으면
        해당 위젯만 스크롤한다. 포커스가 없으면 Text의 기본 휠 동작을 막고 ``fallback``
        스크롤 영역만 직접 움직여 로컬/바깥 스크롤이 동시에 움직이는 것을 방지한다.

        Esc 또는 위젯 바깥의 빈 공간을 클릭하면 로컬 포커스를 해제한다.
        Entry/Combobox 등 다른 위젯이 정상적으로 포커스를 가져간 경우에는 건드리지 않는다.
        """
        root = widget.winfo_toplevel()

        def on_mousewheel(event):
            try:
                try:
                    disabled = str(widget.cget("state")) == "disabled"
                except tk.TclError:
                    disabled = False

                target = widget if (not disabled and widget.focus_get() is widget) else fallback
                if target is None:
                    return "break"

                if getattr(event, "num", None) == 4:
                    target.yview_scroll(-1, "units")
                elif getattr(event, "num", None) == 5:
                    target.yview_scroll(1, "units")
                elif getattr(event, "delta", 0):
                    target.yview_scroll(-1 if event.delta > 0 else 1, "units")
                else:
                    return None
            except tk.TclError:
                return None
            return "break"

        def release_focus(_event=None):
            """Esc로 로컬 스크롤 위젯의 포커스를 빠져나온다."""
            try:
                root.focus_set()
            except tk.TclError:
                pass
            return "break"

        def release_focus_after_outside_click(event):
            """바깥 클릭 뒤에도 포커스가 남아 있을 때만 빈 공간 클릭으로 간주해 해제한다."""
            clicked = getattr(event, "widget", None)
            if clicked is None or clicked is widget:
                return None

            try:
                if clicked.winfo_toplevel() is not root:
                    return None
            except (tk.TclError, AttributeError):
                return None

            def clear_if_still_focused():
                try:
                    if widget.focus_get() is widget:
                        root.focus_set()
                except tk.TclError:
                    pass

            # Tk의 Button-1 기본 동작이 다른 입력 위젯으로 포커스를 옮길 시간을 먼저 준다.
            # 그 뒤에도 이 Text가 포커스를 잡고 있을 때만 강제로 해제한다.
            try:
                root.after_idle(clear_if_still_focused)
            except tk.TclError:
                pass
            return None

        widget.bind("<MouseWheel>", on_mousewheel, add="+")
        widget.bind("<Button-4>", on_mousewheel, add="+")
        widget.bind("<Button-5>", on_mousewheel, add="+")
        widget.bind("<Escape>", release_focus, add="+")
        root.bind_all("<Button-1>", release_focus_after_outside_click, add="+")

    @staticmethod
    def bind_canvas_scrollregion(
        canvas: tk.Canvas,
        content: tk.Misc,
        *,
        window_id: int | None = None,
        fit_width: bool = True,
    ) -> None:
        """Canvas 내부 content의 세로 스크롤 영역을 공용 규칙으로 관리한다.

        내용 높이가 viewport보다 작거나 같으면 빈 여백은 스크롤 영역으로 만들지 않고
        맨 위에 고정한다. 내용이 viewport보다 클 때만 실제 content bbox를 스크롤한다.

        ``window_id``를 주면 Canvas 폭 변경 시 내부 window 폭도 함께 맞춘다.
        """

        def sync_region(_event=None) -> None:
            try:
                canvas.update_idletasks()
                viewport_height = max(1, int(canvas.winfo_height()))
                bbox = canvas.bbox("all")

                if not bbox:
                    canvas.configure(scrollregion=(0, 0, 0, viewport_height))
                    canvas.yview_moveto(0.0)
                    return

                x1, y1, x2, y2 = bbox
                content_height = max(0, int(y2 - y1))

                if content_height <= viewport_height:
                    canvas.configure(
                        scrollregion=(x1, 0, x2, viewport_height)
                    )
                    canvas.yview_moveto(0.0)
                else:
                    canvas.configure(scrollregion=bbox)
            except tk.TclError:
                return

        def sync_canvas(event: tk.Event) -> None:
            try:
                if fit_width and window_id is not None:
                    canvas.itemconfigure(window_id, width=event.width)
            except tk.TclError:
                pass

            # 폭 변경으로 content 높이가 달라질 수 있으므로 같은 규칙을 즉시 재적용한다.
            sync_region()

        content.bind("<Configure>", sync_region, add="+")
        canvas.bind("<Configure>", sync_canvas, add="+")
        canvas.after_idle(sync_region)

    @staticmethod
    def auto_hide_scrollbar(scrollbar: ttk.Scrollbar):
        """스크롤이 필요할 때만 스크롤바를 표시하는 set 콜백을 반환한다.

        Text, Treeview, Canvas 등의 yscrollcommand/xscrollcommand에 연결해서 사용한다.
        grid와 pack 배치 방식을 모두 지원한다.
        """
        manager = ""
        layout_info = None
        visible = True

        def _remember_layout() -> None:
            nonlocal manager, layout_info
            current_manager = scrollbar.winfo_manager()
            if current_manager == "grid":
                manager = "grid"
                layout_info = scrollbar.grid_info()
            elif current_manager == "pack":
                manager = "pack"
                layout_info = scrollbar.pack_info()

        def _set(first, last) -> None:
            nonlocal visible

            # configure()가 grid()/pack()보다 먼저 호출된 경우에도
            # 첫 스크롤 갱신 시 실제 배치 정보를 잡아낸다.
            if scrollbar.winfo_manager():
                _remember_layout()

            first_value = float(first)
            last_value = float(last)
            needs_scroll = first_value > 0.0 or last_value < 1.0

            if needs_scroll and not visible:
                if manager == "grid":
                    scrollbar.grid()
                elif manager == "pack" and layout_info is not None:
                    options = dict(layout_info)
                    options.pop("in", None)
                    scrollbar.pack(**options)
                visible = True
            elif not needs_scroll and visible:
                if manager == "grid":
                    scrollbar.grid_remove()
                    visible = False
                elif manager == "pack":
                    scrollbar.pack_forget()
                    visible = False

            scrollbar.set(first, last)

        return _set

    @classmethod
    def make_scrollable_frame(
        cls,
        master,
        *,
        padding: tuple[int, int] | tuple[int, int, int, int] = (0, 0),
    ) -> tuple[ttk.Frame, tk.Canvas, ttk.Frame, ttk.Scrollbar]:
        """스크롤 가능한 Frame 구성을 생성한다.

        반환값: (wrapper, canvas, content_frame, scrollbar)
        """
        wrapper = ttk.Frame(master)
        canvas = tk.Canvas(wrapper, highlightthickness=0)
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        content = ttk.Frame(canvas, padding=padding)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        canvas.configure(yscrollcommand=cls.auto_hide_scrollbar(scrollbar))
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        cls.bind_canvas_scrollregion(
            canvas,
            content,
            window_id=window_id,
            fit_width=True,
        )
        cls.bind_mousewheel(canvas, canvas)
        return wrapper, canvas, content, scrollbar

