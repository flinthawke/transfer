"""Flint Toolbox 공통 툴팁 동작.

색상/ttk 스타일과 분리된 UI 동작 모듈이다.
프로그램 전체 툴팁을 한 번에 끄거나, 특정 위젯만 제외할 수 있다.
"""
from __future__ import annotations

import weakref

from flinters.gui import tk


class TooltipManager:
    """Flint 툴팁의 전역 동작을 관리한다."""

    enabled = True
    default_delay = 650
    default_wraplength = 320
    _instances: "weakref.WeakSet[ToolTip]" = weakref.WeakSet()

    @classmethod
    def set_enabled(cls, enabled: bool) -> None:
        """False로 설정하면 등록된 툴팁을 포함해 전체 표시를 중지한다."""
        cls.enabled = bool(enabled)
        if not cls.enabled:
            for tooltip in list(cls._instances):
                tooltip.hide()

    @classmethod
    def configure(
        cls,
        *,
        enabled: bool | None = None,
        delay: int | None = None,
        wraplength: int | None = None,
    ) -> None:
        """전역 사용 여부와 기본 대기 시간/폭을 설정한다."""
        if enabled is not None:
            cls.set_enabled(enabled)
        if delay is not None:
            cls.default_delay = max(0, int(delay))
        if wraplength is not None:
            cls.default_wraplength = max(80, int(wraplength))

    @classmethod
    def claim(cls, owner: "ToolTip") -> None:
        """owner만 툴팁 표시 후보로 남기고 다른 예약/표시 툴팁은 모두 닫는다.

        부모 위젯과 자식 위젯에 툴팁이 함께 연결된 경우 Tkinter의 Enter/Leave
        이벤트 특성상 여러 툴팁 예약이 동시에 살아남을 수 있다.
        새 툴팁이 활성화될 때 다른 예약까지 정리해 항상 하나만 표시되게 한다.
        """
        for tooltip in list(cls._instances):
            if tooltip is not owner:
                tooltip.hide()

    @classmethod
    def attach(
        cls,
        widget: tk.Misc,
        text: str,
        *,
        delay: int | None = None,
        wraplength: int | None = None,
        ignore: bool = False,
    ) -> "ToolTip":
        """위젯에 툴팁을 연결한다. ignore=True면 등록하되 표시하지 않는다."""
        tooltip = ToolTip(
            widget,
            text,
            delay=cls.default_delay if delay is None else delay,
            wraplength=cls.default_wraplength if wraplength is None else wraplength,
            ignore=ignore,
        )
        # 객체가 가비지 컬렉션되지 않도록 위젯에 보관한다.
        store = getattr(widget, "_flint_tooltips", None)
        if store is None:
            store = []
            setattr(widget, "_flint_tooltips", store)
        store.append(tooltip)
        cls._instances.add(tooltip)
        return tooltip


class ToolTip:
    """위젯 위에 일정 시간 머물면 간단한 설명을 표시한다."""

    def __init__(
        self,
        widget: tk.Misc,
        text: str,
        *,
        delay: int = 650,
        wraplength: int = 320,
        ignore: bool = False,
    ) -> None:
        self.widget = widget
        self.text = text
        self.delay = max(0, int(delay))
        self.wraplength = max(80, int(wraplength))
        self.ignore = bool(ignore)
        self._after_id: str | None = None
        self._window: tk.Toplevel | None = None

        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")

    @property
    def enabled(self) -> bool:
        return TooltipManager.enabled and not self.ignore and bool(self.text)

    def set_ignored(self, ignore: bool = True) -> None:
        """이 툴팁 하나만 표시 대상에서 제외하거나 다시 활성화한다."""
        self.ignore = bool(ignore)
        if self.ignore:
            self.hide()

    def set_text(self, text: str) -> None:
        self.text = text
        if not text:
            self.hide()

    def _schedule(self, _event=None) -> None:
        self.hide()
        if not self.enabled:
            return

        # 부모/자식 위젯의 Enter 이벤트가 연달아 발생해도
        # 가장 최근에 진입한 위젯 하나만 툴팁 후보로 유지한다.
        TooltipManager.claim(self)

        try:
            self._after_id = self.widget.after(self.delay, self.show)
        except tk.TclError:
            self._after_id = None

    def show(self) -> None:
        self._after_id = None
        if not self.enabled or self._window is not None:
            return

        # 예약 후 다른 위젯의 툴팁이 활성화됐을 가능성까지 방어한다.
        TooltipManager.claim(self)

        try:
            widget_x = self.widget.winfo_rootx()
            widget_y = self.widget.winfo_rooty()
            widget_h = self.widget.winfo_height()
        except tk.TclError:
            return

        try:
            window = tk.Toplevel(self.widget)
            window.wm_overrideredirect(True)
            label = tk.Label(
                window,
                text=self.text,
                justify="left",
                relief="solid",
                borderwidth=1,
                background="#fffbe6",
                foreground="#25313a",
                padx=8,
                pady=5,
                wraplength=self.wraplength,
                font=("Malgun Gothic", 9),
            )
            label.pack()
            window.update_idletasks()

            tooltip_w = max(window.winfo_reqwidth(), 1)
            tooltip_h = max(window.winfo_reqheight(), 1)
            # 툴팁은 모니터 전체가 아니라 현재 프로그램 창 안에서만 표시한다.
            # 하단 버튼처럼 아래 공간이 부족하면 자동으로 위쪽에 띄운다.
            try:
                host = self.widget.winfo_toplevel()
                host.update_idletasks()

                host_x = host.winfo_rootx()
                host_y = host.winfo_rooty()
                host_w = host.winfo_width()
                host_h = host.winfo_height()
            except tk.TclError:
                host_x = 0
                host_y = 0
                host_w = self.widget.winfo_screenwidth()
                host_h = self.widget.winfo_screenheight()

            left = host_x + 4
            top = host_y + 4
            right = host_x + host_w - 4
            bottom = host_y + host_h - 4

            x = widget_x + 14
            y_below = widget_y + widget_h + 7
            y_above = widget_y - tooltip_h - 7

            # 가로 방향: 창 오른쪽을 넘으면 왼쪽으로 당긴다.
            if x + tooltip_w > right:
                x = right - tooltip_w
            x = max(left, x)

            # 세로 방향: 아래에 들어가면 아래, 아니면 위쪽에 표시한다.
            if y_below + tooltip_h <= bottom:
                y = y_below
            elif y_above >= top:
                y = y_above
            else:
                # 위/아래 어느 쪽도 완전히 들어가지 않는 아주 작은 창에서는
                # 가능한 범위 안으로 강제로 맞춘다.
                y = max(top, min(y_below, bottom - tooltip_h))

            window.wm_geometry(f"+{x}+{y}")
            self._window = window
        except tk.TclError:
            try:
                window.destroy()
            except (tk.TclError, UnboundLocalError):
                pass
            self._window = None

    def hide(self, _event=None) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

        if self._window is not None:
            try:
                self._window.destroy()
            except tk.TclError:
                pass
            self._window = None
