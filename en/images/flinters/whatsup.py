"""Flint 계열 작업 상태 표시 공용 모듈.

이 모듈의 역할은 두 가지로 명확히 구분한다.

1. ProgressDialog
   일반적인 장시간 작업의 상태·파일명·개수·진행률을 계속 보여주는 기본 진행창이다.

2. WhatsUp
   기본 상태표시나 진행률만으로는 현재 처리를 표현할 수 없어 프로그램이 멈춘 것처럼
   보이는 구간에서만 잠시 나타나는 보조 외부창이다.
   평소에는 표시하지 않으며 일반 진행상황을 중복해서 보여주는 용도로 사용하지 않는다.
   파일 조사, 원격/가상 드라이브 조사, 해시 비교처럼 진행률이 한동안 움직이지 않는
   내부 처리의 이유를 사용자에게 설명하는 데만 사용한다.

즉, 일반 진행표시는 ProgressDialog 또는 각 프로그램의 기본 상태 UI가 담당하고,
WhatsUp은 그 기본 출력기가 표현하지 못하는 공백 구간만 보충한다.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Callable

from flinters.gui import FlintStyle, tk, tkfont, ttk


class ProgressDialog:
    """상태·카운트·파일명·진행률을 표시하는 공용 진행창."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        title: str,
        heading: str,
        status: str = '',
        cancel_text: str | None = None,
        on_cancel: Callable[[], None] | None = None,
        closable: bool = False,
        width: int = 64,
        bar_length: int = 500,
    ) -> None:
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.transient(parent)
        self.window.resizable(False, False)
        self._closed = False
        self._on_cancel = on_cancel

        if closable:
            self.window.protocol('WM_DELETE_WINDOW', self.close)
        elif on_cancel is not None:
            self.window.protocol('WM_DELETE_WINDOW', self.request_cancel)
        else:
            self.window.protocol('WM_DELETE_WINDOW', lambda: None)

        body = ttk.Frame(self.window, padding=16)
        body.pack(fill='both', expand=True)

        ttk.Label(body, text=heading, style='Section.TLabel').pack(anchor='w')

        self.status_var = tk.StringVar(value=status)
        self.count_var = tk.StringVar(value='')
        self.file_var = tk.StringVar(value='')

        ttk.Label(body, textvariable=self.status_var).pack(anchor='w', pady=(10, 2))
        ttk.Label(body, textvariable=self.count_var).pack(anchor='w')
        ttk.Label(body, textvariable=self.file_var, width=width).pack(anchor='w', pady=(2, 8))

        self.bar = ttk.Progressbar(body, mode='indeterminate', length=bar_length)
        self.bar.pack(fill='x')
        self.bar.start(12)

        self.cancel_button: ttk.Button | None = None
        if cancel_text is not None:
            button_row = ttk.Frame(body)
            button_row.pack(fill='x', pady=(12, 0))
            self.cancel_button = ttk.Button(
                button_row,
                text=cancel_text,
                command=self.request_cancel,
                width=10,
            )
            self.cancel_button.pack(side='right')

        self._center_on_parent()
        self.window.grab_set()

    def _center_on_parent(self) -> None:
        self.window.update_idletasks()
        try:
            x = self.parent.winfo_rootx() + max(
                (self.parent.winfo_width() - self.window.winfo_reqwidth()) // 2,
                0,
            )
            y = self.parent.winfo_rooty() + max(
                (self.parent.winfo_height() - self.window.winfo_reqheight()) // 2,
                0,
            )
            self.window.geometry(f'+{x}+{y}')
        except tk.TclError:
            pass

    def request_cancel(self) -> None:
        if self._closed or self._on_cancel is None:
            return
        self._on_cancel()

    def disable_cancel(self) -> None:
        if self.cancel_button is not None:
            try:
                self.cancel_button.configure(state='disabled')
            except tk.TclError:
                pass

    def set_status(self, text: str) -> None:
        if not self._closed:
            self.status_var.set(text)

    def set_count(self, text: str) -> None:
        if not self._closed:
            self.count_var.set(text)

    def set_file(self, text: str) -> None:
        if not self._closed:
            self.file_var.set(text)

    def set_indeterminate(self) -> None:
        if self._closed:
            return
        if str(self.bar.cget('mode')) != 'indeterminate':
            self.bar.stop()
            self.bar.configure(mode='indeterminate')
            self.bar.start(12)

    def set_progress(self, current: int, total: int) -> None:
        if self._closed:
            return
        maximum = max(total, 1)
        if str(self.bar.cget('mode')) != 'determinate':
            self.bar.stop()
            self.bar.configure(mode='determinate', maximum=maximum, value=0)
        self.bar['maximum'] = maximum
        self.bar['value'] = min(max(current, 0), maximum)

    def pump(self) -> None:
        """동기 작업 중에도 진행창이 즉시 다시 그려지게 한다."""
        if self._closed:
            return
        try:
            self.window.update_idletasks()
            self.window.update()
        except tk.TclError:
            pass

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.bar.stop()
            self.window.grab_release()
            self.window.destroy()
        except tk.TclError:
            pass

class WhatsUp:
    """기본 진행 표시가 설명하지 못하는 긴 공백 구간만 보여주는 보조 안내창.

    작업 스레드는 ``WhatsUp.emit(callback, code, detail)`` 로 이벤트만 보낸다.
    UI에서는 해당 작업이 ``delay_ms`` 이상 계속될 때만 작은 외부창을 띄운다.
    진행률이나 일반 상태표시가 다시 움직이면 ``clear()`` 로 즉시 닫는다.
    """

    EVENT_KIND = "whatsup"
    CLEAR_EVENT_KIND = "whatsup_clear"

    def __init__(
        self,
        parent: tk.Misc,
        *,
        messages: dict[str, str] | None = None,
        prefix: str = "Flint What's Up",
        delay_ms: int = 700,
        freeze_watch: bool = True,
        freeze_seconds: float = 12.0,
        heartbeat_ms: int = 1000,
        force_exit_title: str = "Flint What's Up",
        force_exit_message: str = (
            "프로그램이 응답하지 않습니다.\n강제 종료할까요?\n\n"
            "The program is not responding. Force quit?"
        ),
    ) -> None:
        self.parent = parent
        self.messages = dict(messages or {})
        self.prefix = prefix
        self.delay_ms = max(0, int(delay_ms))

        # Tk 이벤트 루프와 독립된 watchdog이 마지막 heartbeat를 감시한다.
        # 메인 Tk가 멎어도 Windows 네이티브 MessageBox는 별도 스레드에서 살아 있으므로
        # 사용자가 최종적으로 프로세스를 강제 종료할 수 있다.
        self.freeze_watch = bool(freeze_watch)
        self.freeze_seconds = max(float(freeze_seconds), 3.0)
        self.heartbeat_ms = max(int(heartbeat_ms), 250)
        self.force_exit_title = str(force_exit_title)
        self.force_exit_message = str(force_exit_message)
        self._heartbeat_lock = threading.Lock()
        self._last_heartbeat = time.monotonic()
        self._watchdog_stop = threading.Event()
        self._watchdog_active = threading.Event()
        self._watchdog_prompt_open = threading.Event()
        self._heartbeat_after_id = None
        self._watchdog_thread: threading.Thread | None = None

        self.window: tk.Toplevel | None = None
        self.var: tk.StringVar | None = None
        self.display_var: tk.StringVar | None = None
        self.bar: ttk.Progressbar | None = None
        self._after_id = None
        self._pending: tuple[str, str] | None = None

        if self.freeze_watch:
            self._start_watchdog()

    def start_watch(self) -> None:
        """작업 시작 시 감시를 활성화하고 이전 대기시간을 초기화한다."""
        if not self.freeze_watch or self._watchdog_stop.is_set():
            return
        with self._heartbeat_lock:
            self._last_heartbeat = time.monotonic()
            self._watchdog_active.set()

    def stop_watch(self) -> None:
        """작업 완료·취소·오류 후 감시를 비활성화한다."""
        self._watchdog_active.clear()

    def _touch_heartbeat(self) -> None:
        """Tk 메인 이벤트 루프가 살아 있음을 watchdog에 알린다."""
        if self._watchdog_stop.is_set():
            return
        with self._heartbeat_lock:
            self._last_heartbeat = time.monotonic()
        try:
            self._heartbeat_after_id = self.parent.after(self.heartbeat_ms, self._touch_heartbeat)
        except tk.TclError:
            self._heartbeat_after_id = None

    def _start_watchdog(self) -> None:
        self._touch_heartbeat()
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            name="FlintWhatsUpWatchdog",
            daemon=True,
        )
        self._watchdog_thread.start()

    def _watchdog_loop(self) -> None:
        """Tk와 독립적으로 heartbeat 정지를 감시한다."""
        interval = min(max(self.freeze_seconds / 4.0, 0.5), 2.0)
        while not self._watchdog_stop.wait(interval):
            with self._heartbeat_lock:
                elapsed = time.monotonic() - self._last_heartbeat
            if (not self._watchdog_active.is_set()
                    or elapsed < self.freeze_seconds
                    or self._watchdog_prompt_open.is_set()):
                continue
            self._watchdog_prompt_open.set()
            try:
                self._offer_force_exit()
            finally:
                self._watchdog_prompt_open.clear()
                # 사용자가 종료하지 않았다면 즉시 재경고하지 않고 새 유예시간을 준다.
                with self._heartbeat_lock:
                    self._last_heartbeat = time.monotonic()

    def _offer_force_exit(self) -> None:
        """Tk가 얼어도 동작하는 Windows 네이티브 비상 종료 확인창을 띄운다."""
        if os.name != "nt":
            return
        try:
            import ctypes

            MB_YESNO = 0x00000004
            MB_ICONWARNING = 0x00000030
            MB_SYSTEMMODAL = 0x00001000
            MB_TOPMOST = 0x00040000
            IDYES = 6
            result = ctypes.windll.user32.MessageBoxW(
                None,
                self.force_exit_message,
                self.force_exit_title,
                MB_YESNO | MB_ICONWARNING | MB_SYSTEMMODAL | MB_TOPMOST,
            )
            if int(result) == IDYES:
                # 의도적인 최종 비상탈출. finally/설정 저장을 기다리지 않는다.
                os._exit(70)
        except Exception:
            # watchdog 자체 오류가 본 프로그램을 죽이지 않게 한다.
            return

    @classmethod
    def emit(cls, callback: Callable[[tuple], None], code: str, detail: object = "") -> None:
        """작업 스레드에서 UI에 전달할 What's Up 이벤트를 만든다."""
        callback((cls.EVENT_KIND, str(code), str(detail) if detail is not None else ""))

    @classmethod
    def emit_clear(cls, callback: Callable[[tuple], None]) -> None:
        """작업 스레드에서 열린 What's Up 표시를 닫으라는 이벤트를 보낸다."""
        callback((cls.CLEAR_EVENT_KIND,))

    @classmethod
    def is_event(cls, event: tuple) -> bool:
        return bool(event) and event[0] == cls.EVENT_KIND

    def set_messages(self, messages: dict[str, str]) -> None:
        self.messages = dict(messages)

    def format(self, code: str, detail: str = "") -> str:
        message = str(self.messages.get(code, code))
        if detail:
            message += f"\n{detail}"
        return message

    def _cancel_pending(self) -> None:
        if self._after_id is None:
            return
        try:
            self.parent.after_cancel(self._after_id)
        except tk.TclError:
            pass
        self._after_id = None

    def _place_window(self) -> None:
        if self.window is None:
            return
        try:
            self.window.update_idletasks()
            parent = self.parent.winfo_toplevel()
            x = parent.winfo_rootx() + max(0, (parent.winfo_width() - self.window.winfo_width()) // 2)
            y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self.window.winfo_height()) // 2)
            self.window.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass

    def _show_pending(self) -> None:
        self._after_id = None
        if self._pending is None:
            return

        code, detail = self._pending
        message = self.format(code, detail)

        try:
            if self.window is not None and self.window.winfo_exists():
                if self.var is not None:
                    self.var.set(message)
                self._place_window()
                return
        except tk.TclError:
            self.window = None

        try:
            parent = self.parent.winfo_toplevel()
            self.window = tk.Toplevel(parent)
            self.window.title(self.prefix)
            self.window.transient(parent)
            self.window.resizable(False, False)
            self.window.protocol("WM_DELETE_WINDOW", self.clear)

            frame = ttk.Frame(self.window, padding=(18, 14))
            frame.pack(fill="both", expand=True)

            self.var = tk.StringVar(master=self.window, value=message)
            self.display_var = tk.StringVar(master=self.window, value="")

            # WhatsUp 본문 폭은 240px로 고정한다. 문장은 두 줄까지 자연스럽게
            # 감싸고 그보다 길 때만 마지막 보이는 줄 끝을 ... 처리한다.
            text_font = tkfont.Font(master=self.window, font=FlintStyle.NORMAL_FONT)
            text_height = text_font.metrics("linespace") * 2
            message_area = ttk.Frame(frame, width=240, height=text_height)
            message_area.pack(fill="x")
            message_area.pack_propagate(False)

            message_label = ttk.Label(
                message_area,
                textvariable=self.display_var,
                anchor="center",
                justify="center",
                wraplength=240,
            )
            message_label.pack(fill="both", expand=True)

            self.bar = ttk.Progressbar(
                frame,
                mode="indeterminate",
                length=240,
                style="Silver.Horizontal.TProgressbar",
            )
            self.bar.pack(fill="x", pady=(12, 0))
            self.bar.start(12)
            FlintStyle.bind_wrapped_ellipsis(
                message_label,
                self.var,
                self.display_var,
                max_lines=2,
            )

            self._place_window()
        except tk.TclError:
            self.window = None
            self.var = None
            self.display_var = None
            self.bar = None

    def set(self, code: str, detail: str = "") -> None:
        """긴 공백이 계속될 때만 보이도록 새 안내를 지연 예약한다.

        연속된 What's Up 이벤트는 같은 공백 구간의 진행으로 본다. 이미 표시 예약이
        걸려 있으면 내용만 갱신하고 최초 예약 시점은 유지한다. 그래야 해시 비교처럼
        짧은 이벤트가 연속될 때마다 지연 시간이 처음부터 다시 시작되지 않는다.
        """
        self._pending = (str(code), str(detail))

        try:
            if self.window is not None and self.window.winfo_exists():
                if self.var is not None:
                    self.var.set(self.format(*self._pending))
                return
        except tk.TclError:
            self.window = None

        # 이미 첫 이벤트에서 표시 예약이 걸렸다면 그 시점을 유지한다.
        # 이후 이벤트는 _pending 내용만 바꾸며 clear()가 오면 예약도 함께 취소된다.
        if self._after_id is not None:
            return

        try:
            self._after_id = self.parent.after(self.delay_ms, self._show_pending)
        except tk.TclError:
            self._after_id = None

    def handle_event(self, event: tuple) -> bool:
        """What's Up 표시/해제 이벤트를 처리하면 True를 반환한다."""
        if not event:
            return False
        if event[0] == self.CLEAR_EVENT_KIND:
            self.clear()
            return True
        if not self.is_event(event):
            return False
        _kind, code, detail = event
        self.set(code, detail)
        return True

    def clear(self) -> None:
        """대기 중인 표시를 취소하고 열린 안내창도 즉시 닫는다."""
        self._pending = None
        self._cancel_pending()

        if self.bar is not None:
            try:
                self.bar.stop()
            except tk.TclError:
                pass

        if self.window is not None:
            try:
                self.window.destroy()
            except tk.TclError:
                pass

        self.window = None
        self.var = None
        self.bar = None

    def destroy(self) -> None:
        """WhatsUp 표시와 watchdog을 함께 종료한다."""
        self.clear()
        self._watchdog_active.clear()
        self._watchdog_stop.set()
        if self._heartbeat_after_id is not None:
            try:
                self.parent.after_cancel(self._heartbeat_after_id)
            except tk.TclError:
                pass
            self._heartbeat_after_id = None

