"""Flint 공용 텍스트 편집기.

Flint 프로그램에서 반복해서 사용하는 Text 편집 기능을 한곳에 모은다.

제공 기능
- 잘라내기 / 복사 / 붙여넣기 / 전체 선택
- 실행 취소 / 다시 실행
- 찾기 / 바꾸기 / 모두 바꾸기
- 다음 찾기 / 이전 찾기
- 줄 번호로 이동
- 현재 줄 복제 / 삭제
- 들여쓰기 / 내어쓰기
- 선택 영역 대소문자 변환
- 줄 바꿈 켜기 / 끄기
- 글자 크기 확대 / 축소 / 초기화
- Ctrl+S 저장 콜백 연결
- 우클릭 메뉴
- 자동 숨김 스크롤바
"""
from __future__ import annotations

from collections.abc import Callable

from flinters.gui import FlintStyle, tk, ttk


# ------------------------------------------------------------------
# 선택 장착형 편집 기능
# ------------------------------------------------------------------

def _keep_feature(widget: tk.Text, feature: object) -> object:
    """위젯 수명 동안 선택 장착형 기능 객체를 유지한다."""
    features = getattr(widget, "_flint_attached_features", None)
    if features is None:
        features = []
        setattr(widget, "_flint_attached_features", features)
    features.append(feature)
    return feature


def _select_all_text(text: tk.Text) -> str:
    """Text 전체 선택 공용 동작."""
    text.tag_add("sel", "1.0", "end-1c")
    text.mark_set("insert", "end-1c")
    text.see("insert")
    return "break"


def _position_context_click(text: tk.Text, event) -> None:
    """선택 영역 밖을 우클릭했을 때만 커서와 선택을 갱신한다."""
    click_index = text.index(f"@{event.x},{event.y}")
    try:
        first = text.index("sel.first")
        last = text.index("sel.last")
        inside = text.compare(first, "<=", click_index) and text.compare(click_index, "<", last)
    except tk.TclError:
        inside = False
    if not inside:
        text.mark_set("insert", click_index)
        text.tag_remove("sel", "1.0", "end")


def _flint_menu(master: tk.Misc) -> tk.Menu:
    """Flint 색상표를 적용한 공용 우클릭 메뉴."""
    return tk.Menu(
        master, tearoff=False,
        background=FlintStyle.FIELD,
        foreground=FlintStyle.TEXT,
        activebackground=FlintStyle.SEA,
        activeforeground="#ffffff",
        selectcolor=FlintStyle.SEA,
        disabledforeground=FlintStyle.SUBTEXT,
        relief="flat",
        borderwidth=1,
        activeborderwidth=0,
        font=("맑은 고딕", 10),
    )


class FlintContextMenuFeature:
    """기존 tk.Text에 기본 우클릭 편집 메뉴만 장착한다."""

    def __init__(self, text: tk.Text, *, read_only: bool = False) -> None:
        self.text = text
        self.read_only = read_only
        self.menu = _flint_menu(text)
        self._build_menu()
        text.bind("<Button-3>", self._show, add="+")

    def _event(self, sequence: str) -> str:
        self.text.focus_set()
        self.text.event_generate(sequence)
        return "break"

    def _select_all(self) -> str:
        return _select_all_text(self.text)

    def _build_menu(self) -> None:
        if not self.read_only:
            self.menu.add_command(
                label="실행 취소", accelerator="Ctrl+Z",
                command=lambda: self._event("<<Undo>>"),
            )
            self.menu.add_command(
                label="다시 실행", accelerator="Ctrl+Y",
                command=lambda: self._event("<<Redo>>"),
            )
            self.menu.add_separator()
            self.menu.add_command(
                label="잘라내기", accelerator="Ctrl+X",
                command=lambda: self._event("<<Cut>>"),
            )

        self.menu.add_command(
            label="복사하기", accelerator="Ctrl+C",
            command=lambda: self._event("<<Copy>>"),
        )
        if not self.read_only:
            self.menu.add_command(
                label="붙여넣기", accelerator="Ctrl+V",
                command=lambda: self._event("<<Paste>>"),
            )
        self.menu.add_command(
            label="전체 선택", accelerator="Ctrl+A", command=self._select_all
        )

    def _show(self, event) -> str:
        _position_context_click(self.text, event)
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()
        return "break"


def _find_text_match(text: tk.Text, query: str, tag: str, *, backwards: bool = False) -> str | None:
    """선택 장착형 찾기와 전체 편집기의 공통 검색·강조 엔진."""
    text.tag_remove(tag, "1.0", "end")
    if not query:
        return None
    if backwards:
        start = text.index(f"insert-{len(query)}c")
        found = text.search(query, start, stopindex="1.0", backwards=True, nocase=True)
        if not found:
            found = text.search(query, "end-1c", stopindex=start, backwards=True, nocase=True)
    else:
        start = text.index("insert")
        found = text.search(query, start, stopindex="end", nocase=True)
        if not found:
            found = text.search(query, "1.0", stopindex=start, nocase=True)
    if not found:
        return None
    end = text.index(f"{found}+{len(query)}c")
    text.tag_add(tag, found, end)
    text.mark_set("insert", end)
    text.see(found)
    return str(found)


class FlintFindFeature:
    """기존 tk.Text에 찾기 기능(Ctrl+F/F3/Shift+F3)만 장착한다."""

    TAG = "_flint_attached_find_match"

    def __init__(self, text: tk.Text, *, owner: tk.Misc | None = None) -> None:
        self.text = text
        self.owner = owner or text.winfo_toplevel()
        self.window: tk.Toplevel | None = None
        self.entry: ttk.Entry | None = None
        self.last_query = ""
        text.tag_configure(self.TAG, background="#ffe58a", foreground="#202020")
        text.bind("<Control-f>", self.open, add="+")
        text.bind("<Control-F>", self.open, add="+")
        text.bind("<F3>", self.next, add="+")
        text.bind("<Shift-F3>", self.previous, add="+")

    def _clear(self) -> None:
        self.text.tag_remove(self.TAG, "1.0", "end")

    def _find(self, query: str, *, backwards: bool = False) -> str | None:
        if query:
            self.last_query = query
        return _find_text_match(self.text, query, self.TAG, backwards=backwards)

    def next(self, _event=None) -> str:
        query = self.entry.get() if self.entry is not None else self.last_query
        self._find(query)
        return "break"

    def previous(self, _event=None) -> str:
        query = self.entry.get() if self.entry is not None else self.last_query
        self._find(query, backwards=True)
        return "break"

    def open(self, _event=None) -> str:
        if self.window is not None:
            try:
                if self.window.winfo_exists():
                    self.window.deiconify()
                    self.window.lift()
                    if self.entry is not None:
                        self.entry.focus_set()
                        self.entry.selection_range(0, "end")
                    return "break"
            except tk.TclError:
                pass

        win = tk.Toplevel(self.owner)
        win.title("찾기")
        win.resizable(False, False)
        self.window = win

        body = ttk.Frame(win, padding=10)
        body.grid(row=0, column=0, sticky="nsew")
        ttk.Label(body, text="찾을 문자열").grid(row=0, column=0, padx=(0, 8))
        entry = ttk.Entry(body, width=36)
        entry.grid(row=0, column=1, sticky="ew")
        self.entry = entry
        status = ttk.Label(body, text="")
        status.grid(row=1, column=0, columnspan=2, sticky="w", pady=(7, 0))

        def do_find(backwards=False):
            query = entry.get()
            if not query:
                status.configure(text="찾을 문자열을 입력하세요.")
                return "break"
            status.configure(text="" if self._find(query, backwards=backwards) else "찾을 문자열이 없습니다.")
            entry.focus_set()
            return "break"

        buttons = ttk.Frame(body)
        buttons.grid(row=2, column=0, columnspan=2, sticky="e", pady=(9, 0))
        FlintStyle.button(
            buttons, text="이전 찾기", command=lambda: do_find(True), kind="emerald"
        ).pack(side="left")
        FlintStyle.button(
            buttons, text="다음 찾기", command=lambda: do_find(False), kind="emerald"
        ).pack(side="left", padx=(5, 0))

        def close(_event=None):
            self._clear()
            self.window = None
            self.entry = None
            win.destroy()
            return "break"

        entry.bind("<Return>", lambda e: do_find(False))
        entry.bind("<Shift-Return>", lambda e: do_find(True))
        win.bind("<F3>", lambda e: do_find(False))
        win.bind("<Shift-F3>", lambda e: do_find(True))
        win.bind("<Escape>", close)
        win.protocol("WM_DELETE_WINDOW", close)
        entry.focus_set()
        if self.last_query:
            entry.insert(0, self.last_query)
            entry.selection_range(0, "end")
        return "break"


class FlintZoomFeature:
    """기존 tk.Text에 Ctrl + +/-/0 글자 확대·축소 기능만 장착한다."""

    def __init__(self, text: tk.Text, *, bind_keys: bool = True) -> None:
        self.text = text
        self.family, self.size = self._read_font()
        self.default_size = self.size
        if bind_keys:
            text.bind("<Control-plus>", self.zoom_in, add="+")
            text.bind("<Control-equal>", self.zoom_in, add="+")
            text.bind("<Control-minus>", self.zoom_out, add="+")
            text.bind("<Control-0>", self.zoom_reset, add="+")

    def _read_font(self) -> tuple[str, int]:
        try:
            value = self.text.cget("font")
            actual = self.text.tk.call("font", "actual", value)
            data = dict(zip(actual[::2], actual[1::2]))
            return str(data.get("-family", "TkFixedFont")), abs(int(data.get("-size", 10)))
        except Exception:
            return "TkFixedFont", 10

    def _apply(self) -> None:
        self.text.configure(font=(self.family, self.size))

    def zoom_in(self, _event=None) -> str:
        self.size = min(48, self.size + 1)
        self._apply()
        return "break"

    def zoom_out(self, _event=None) -> str:
        self.size = max(6, self.size - 1)
        self._apply()
        return "break"

    def zoom_reset(self, _event=None) -> str:
        self.size = self.default_size
        self._apply()
        return "break"


def attach_context_menu(text: tk.Text, *, read_only: bool = False) -> FlintContextMenuFeature:
    """기존 Text에 기능을 중복 바인딩 없이 장착한다."""
    existing = getattr(text, "_flint_context_feature", None)
    if existing is not None:
        return existing
    feature = FlintContextMenuFeature(text, read_only=read_only)
    setattr(text, "_flint_context_feature", feature)
    return _keep_feature(text, feature)


def attach_find(text: tk.Text, *, owner: tk.Misc | None = None) -> FlintFindFeature:
    """기존 Text에 기능을 중복 바인딩 없이 장착한다."""
    existing = getattr(text, "_flint_find_feature", None)
    if existing is not None:
        return existing
    feature = FlintFindFeature(text, owner=owner)
    setattr(text, "_flint_find_feature", feature)
    return _keep_feature(text, feature)


def attach_zoom(text: tk.Text) -> FlintZoomFeature:
    """기존 Text에 기능을 중복 바인딩 없이 장착한다."""
    existing = getattr(text, "_flint_zoom_feature", None)
    if existing is not None:
        return existing
    feature = FlintZoomFeature(text)
    setattr(text, "_flint_zoom_feature", feature)
    return _keep_feature(text, feature)


def attach_editor_tools(
    text: tk.Text,
    *,
    owner: tk.Misc | None = None,
    read_only: bool = False,
    context_menu: bool = True,
    find: bool = True,
    zoom: bool = True,
) -> list[object]:
    """기존 Text에 필요한 Flint 편집 기능을 선택해서 한 번에 장착한다."""
    attached: list[object] = []
    if context_menu:
        attached.append(attach_context_menu(text, read_only=read_only))
    if find:
        attached.append(attach_find(text, owner=owner))
    if zoom:
        attached.append(attach_zoom(text))
    return attached

# ------------------------------------------------------------------
# 기존 tk.Text에 고급 편집 기능 장착 (상속 없음)
# ------------------------------------------------------------------

class FlintEditorTools:
    """기존 tk.Text에 전체 편집 도구를 연결하는 선택형 컨트롤러."""

    def __getattr__(self, name):
        return getattr(self.text, name)

    FIND_TAG = "_flint_find_match"

    def __init__(self, text: tk.Text, *, owner=None, read_only_tools=False,
                 before_mutation=None, on_save=None):
        self.text = text
        if not read_only_tools:
            text.configure(undo=True)

        self._flint_owner = owner or self.winfo_toplevel()
        self._flint_read_only_tools = read_only_tools
        self._flint_before_mutation = before_mutation
        self._flint_on_save = on_save

        self._flint_context_menu: tk.Menu | None = None
        self._flint_find_window: tk.Toplevel | None = None
        self._flint_find_entry: ttk.Entry | None = None
        self._flint_replace_entry: ttk.Entry | None = None
        self._flint_last_query = ""

        self._flint_original_wrap = str(self.cget("wrap"))
        self._flint_wrap_var = tk.BooleanVar(master=text, value=self._flint_original_wrap != "none")
        self._zoom_feature = FlintZoomFeature(text, bind_keys=False)

        self.tag_configure(self.FIND_TAG, background="#ffe58a", foreground="#202020")
        self._attach_edit_tools()

    # ------------------------------------------------------------------
    # 외부 연결
    # ------------------------------------------------------------------
    def set_before_mutation(self, callback: Callable[[], None] | None) -> None:
        self._flint_before_mutation = callback

    def set_save_callback(self, callback: Callable[[], None] | None) -> None:
        self._flint_on_save = callback

    def _before_mutation(self) -> None:
        if self._flint_before_mutation is not None:
            self._flint_before_mutation()

    def _save(self, _event=None) -> str:
        if self._flint_on_save is not None:
            self._flint_on_save()
        return "break"

    # ------------------------------------------------------------------
    # 기본 편집
    # ------------------------------------------------------------------
    def _run_edit_event(self, sequence: str) -> str:
        if not self._flint_read_only_tools and sequence in {
            "<<Cut>>", "<<Paste>>", "<<Clear>>"
        }:
            self._before_mutation()
        self.focus_set()
        self.event_generate(sequence)
        return "break"

    def undo_edit(self, _event=None) -> str:
        if self._flint_read_only_tools:
            return "break"
        self._before_mutation()
        try:
            self.edit_undo()
        except tk.TclError:
            pass
        return "break"

    def redo_edit(self, _event=None) -> str:
        if self._flint_read_only_tools:
            return "break"
        self._before_mutation()
        try:
            self.edit_redo()
        except tk.TclError:
            pass
        return "break"

    def _select_all(self, _event=None) -> str:
        return _select_all_text(self.text)

    def _show_context_menu(self, event) -> str:
        _position_context_click(self.text, event)

        if self._flint_context_menu is not None:
            try:
                self._flint_context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self._flint_context_menu.grab_release()
        return "break"

    # ------------------------------------------------------------------
    # 줄 편집
    # ------------------------------------------------------------------
    def duplicate_line(self, _event=None) -> str:
        if self._flint_read_only_tools:
            return "break"
        self._before_mutation()
        start = self.index("insert linestart")
        end = self.index("insert lineend+1c")
        text = self.get(start, end)
        if end == self.index("end"):
            text = "\n" + self.get(start, "insert lineend")
            self.insert("insert lineend", text)
        else:
            self.insert(end, text)
        return "break"

    def delete_line(self, _event=None) -> str:
        if self._flint_read_only_tools:
            return "break"
        self._before_mutation()
        start = self.index("insert linestart")
        end = self.index("insert lineend+1c")
        self.delete(start, end)
        return "break"

    def indent_selection(self, _event=None) -> str:
        if self._flint_read_only_tools:
            return "break"
        self._before_mutation()
        start, end = self._selected_line_range()
        line = int(start.split(".")[0])
        last = int(end.split(".")[0])
        for n in range(line, last + 1):
            self.insert(f"{n}.0", "    ")
        return "break"

    def unindent_selection(self, _event=None) -> str:
        if self._flint_read_only_tools:
            return "break"
        self._before_mutation()
        start, end = self._selected_line_range()
        line = int(start.split(".")[0])
        last = int(end.split(".")[0])
        for n in range(line, last + 1):
            value = self.get(f"{n}.0", f"{n}.4")
            if value.startswith("\t"):
                self.delete(f"{n}.0", f"{n}.1")
            else:
                spaces = len(value) - len(value.lstrip(" "))
                if spaces:
                    self.delete(f"{n}.0", f"{n}.{min(spaces, 4)}")
        return "break"

    def _selected_line_range(self) -> tuple[str, str]:
        try:
            start = self.index("sel.first linestart")
            # 선택 끝이 다음 줄 0열이면 그 전 줄까지만 처리
            raw_end = self.index("sel.last")
            if raw_end.endswith(".0") and self.compare(raw_end, ">", start):
                end = self.index(f"{raw_end}-1c linestart")
            else:
                end = self.index("sel.last linestart")
        except tk.TclError:
            start = end = self.index("insert linestart")
        return start, end

    def uppercase_selection(self) -> str:
        return self._transform_selection(str.upper)

    def lowercase_selection(self) -> str:
        return self._transform_selection(str.lower)

    def _transform_selection(self, transform: Callable[[str], str]) -> str:
        if self._flint_read_only_tools:
            return "break"
        try:
            start, end = self.index("sel.first"), self.index("sel.last")
        except tk.TclError:
            return "break"
        self._before_mutation()
        text = transform(self.get(start, end))
        self.delete(start, end)
        self.insert(start, text)
        self.tag_add("sel", start, f"{start}+{len(text)}c")
        return "break"

    # ------------------------------------------------------------------
    # 찾기 / 바꾸기
    # ------------------------------------------------------------------
    def _clear_find_highlight(self) -> None:
        self.tag_remove(self.FIND_TAG, "1.0", "end")

    def _find(self, query: str, *, backwards: bool = False) -> str | None:
        if query:
            self._flint_last_query = query
        return _find_text_match(self.text, query, self.FIND_TAG, backwards=backwards)

    def find_next(self, _event=None) -> str:
        if self._flint_find_entry is not None:
            query = self._flint_find_entry.get()
        else:
            query = self._flint_last_query
        self._find(query, backwards=False)
        return "break"

    def find_previous(self, _event=None) -> str:
        if self._flint_find_entry is not None:
            query = self._flint_find_entry.get()
        else:
            query = self._flint_last_query
        self._find(query, backwards=True)
        return "break"

    def open_find(self, _event=None) -> str:
        existing = self._flint_find_window
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.deiconify()
                    existing.lift()
                    if self._flint_find_entry is not None:
                        self._flint_find_entry.focus_set()
                        self._flint_find_entry.selection_range(0, "end")
                    return "break"
            except tk.TclError:
                pass

        win = tk.Toplevel(self._flint_owner)
        win.title("찾기" if self._flint_read_only_tools else "찾기 / 바꾸기")
        win.resizable(False, False)
        self._flint_find_window = win

        body = ttk.Frame(win, padding=10)
        body.grid(row=0, column=0, sticky="nsew")

        ttk.Label(body, text="찾을 문자열").grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        find_entry = ttk.Entry(body, width=36)
        find_entry.grid(row=0, column=1, columnspan=3, sticky="ew")
        self._flint_find_entry = find_entry

        replace_entry = None
        if not self._flint_read_only_tools:
            ttk.Label(body, text="바꿀 문자열").grid(
                row=1, column=0, sticky="w", padx=(0, 8), pady=(7, 0)
            )
            replace_entry = ttk.Entry(body, width=36)
            replace_entry.grid(
                row=1, column=1, columnspan=3, sticky="ew", pady=(7, 0)
            )
            self._flint_replace_entry = replace_entry

        status = ttk.Label(body, text="")
        status.grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(7, 0)
        )

        def do_find(backwards=False):
            query = find_entry.get()
            if not query:
                status.configure(text="찾을 문자열을 입력하세요.")
                return "break"
            found = self._find(query, backwards=backwards)
            status.configure(text="" if found else "찾을 문자열이 없습니다.")
            find_entry.focus_set()  # 편집기로 포커스가 탈출하지 않음
            return "break"

        def replace_one():
            query = find_entry.get()
            replacement = replace_entry.get() if replace_entry else ""
            if not query:
                status.configure(text="찾을 문자열을 입력하세요.")
                return "break"

            ranges = self.tag_ranges(self.FIND_TAG)
            if ranges and self.get(ranges[0], ranges[1]).casefold() != query.casefold():
                self._clear_find_highlight()
                ranges = ()
            if not ranges:
                if not self._find(query):
                    status.configure(text="찾을 문자열이 없습니다.")
                    return "break"
                ranges = self.tag_ranges(self.FIND_TAG)

            start, end = str(ranges[0]), str(ranges[1])
            self._before_mutation()
            self.delete(start, end)
            self.insert(start, replacement)
            self.mark_set("insert", f"{start}+{len(replacement)}c")
            self._clear_find_highlight()
            self._find(query)
            status.configure(text="1개 바꿈")
            find_entry.focus_set()
            return "break"

        def replace_all():
            query = find_entry.get()
            replacement = replace_entry.get() if replace_entry else ""
            if not query:
                status.configure(text="찾을 문자열을 입력하세요.")
                return "break"

            # 먼저 일치 항목이 있는지 확인하여 빈 치환으로 변경 콜백을 호출하지 않는다.
            if not self.search(query, "1.0", stopindex="end", nocase=True):
                status.configure(text="0개 바꿈")
                find_entry.focus_set()
                return "break"
            self._before_mutation()
            count = 0
            pos = "1.0"
            while True:
                found = self.search(query, pos, stopindex="end", nocase=True)
                if not found:
                    break
                end = self.index(f"{found}+{len(query)}c")
                self.delete(found, end)
                self.insert(found, replacement)
                pos = self.index(f"{found}+{len(replacement)}c")
                count += 1

            self._clear_find_highlight()
            status.configure(text=f"{count}개 바꿈")
            find_entry.focus_set()
            return "break"

        button_row = 3
        previous_button = FlintStyle.button(
            body,
            text="이전 찾기",
            command=lambda: do_find(True),
            kind="emerald",
        )
        previous_button.grid(row=button_row, column=0, pady=(9, 0), sticky="w")

        next_button = FlintStyle.button(
            body,
            text="다음 찾기",
            command=lambda: do_find(False),
            kind="emerald",
        )
        next_button.grid(row=button_row, column=1, pady=(9, 0), padx=(5, 0))

        if not self._flint_read_only_tools:
            replace_button = FlintStyle.button(
                body,
                text="바꾸기",
                command=replace_one,
                kind="emerald",
            )
            replace_button.grid(row=button_row, column=2, pady=(9, 0), padx=(5, 0))

            replace_all_button = FlintStyle.button(
                body,
                text="모두 바꾸기",
                command=replace_all,
                kind="sea",
            )
            replace_all_button.grid(row=button_row, column=3, pady=(9, 0), padx=(5, 0))

        def close_find(_event=None):
            self._clear_find_highlight()
            self._flint_find_window = None
            self._flint_find_entry = None
            self._flint_replace_entry = None
            win.destroy()
            return "break"

        find_entry.bind("<Return>", lambda e: do_find(False))
        find_entry.bind("<Shift-Return>", lambda e: do_find(True))
        if replace_entry is not None:
            replace_entry.bind("<Return>", lambda e: replace_one())
        win.bind("<F3>", lambda e: do_find(False))
        win.bind("<Shift-F3>", lambda e: do_find(True))
        win.bind("<Escape>", close_find)
        win.protocol("WM_DELETE_WINDOW", close_find)

        find_entry.focus_set()
        if self._flint_last_query:
            find_entry.insert(0, self._flint_last_query)
            find_entry.selection_range(0, "end")
        return "break"

    # ------------------------------------------------------------------
    # 줄 이동
    # ------------------------------------------------------------------
    def open_goto_line(self, _event=None) -> str:
        win = tk.Toplevel(self._flint_owner)
        win.title("줄 이동")
        win.resizable(False, False)

        body = ttk.Frame(win, padding=10)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="줄 번호").grid(row=0, column=0, padx=(0, 8))
        entry = ttk.Entry(body, width=12)
        entry.grid(row=0, column=1)

        def go(_event=None):
            try:
                line = max(1, int(entry.get()))
            except ValueError:
                return "break"
            last = int(self.index("end-1c").split(".")[0])
            line = min(line, last)
            self.mark_set("insert", f"{line}.0")
            self.see(f"{line}.0")
            self.focus_set()
            win.destroy()
            return "break"

        go_button = FlintStyle.button(
            body,
            text="이동",
            command=go,
            kind="emerald",
        )
        go_button.grid(row=1, column=1, sticky="e", pady=(8, 0))
        entry.bind("<Return>", go)
        entry.bind("<Escape>", lambda e: win.destroy())
        entry.focus_set()
        return "break"

    # ------------------------------------------------------------------
    # 표시 기능
    # ------------------------------------------------------------------
    def toggle_wrap(self) -> None:
        enabled = bool(self._flint_wrap_var.get())
        if enabled:
            target = self._flint_original_wrap
            if target == "none":
                target = "word"
        else:
            target = "none"
        self.configure(wrap=target)

    def zoom_in(self, _event=None) -> str:
        return self._zoom_feature.zoom_in(_event)

    def zoom_out(self, _event=None) -> str:
        return self._zoom_feature.zoom_out(_event)

    def zoom_reset(self, _event=None) -> str:
        return self._zoom_feature.zoom_reset(_event)

    # ------------------------------------------------------------------
    # 메뉴 / 단축키
    # ------------------------------------------------------------------
    def _attach_edit_tools(self) -> None:
        menu = _flint_menu(self.text)

        if not self._flint_read_only_tools:
            menu.add_command(
                label="실행 취소", accelerator="Ctrl+Z", command=self.undo_edit
            )
            menu.add_command(
                label="다시 실행", accelerator="Ctrl+Y", command=self.redo_edit
            )
            menu.add_separator()
            menu.add_command(
                label="잘라내기",
                accelerator="Ctrl+X",
                command=lambda: self._run_edit_event("<<Cut>>"),
            )

        menu.add_command(
            label="복사하기",
            accelerator="Ctrl+C",
            command=lambda: self._run_edit_event("<<Copy>>"),
        )

        if not self._flint_read_only_tools:
            menu.add_command(
                label="붙여넣기",
                accelerator="Ctrl+V",
                command=lambda: self._run_edit_event("<<Paste>>"),
            )

        menu.add_command(
            label="전체 선택", accelerator="Ctrl+A", command=self._select_all
        )
        menu.add_separator()
        menu.add_command(
            label="찾기 / 바꾸기" if not self._flint_read_only_tools else "찾기",
            accelerator="Ctrl+F",
            command=self.open_find,
        )
        menu.add_command(
            label="줄 이동", accelerator="Ctrl+G", command=self.open_goto_line
        )

        if not self._flint_read_only_tools:
            menu.add_separator()
            menu.add_command(
                label="현재 줄 복제",
                accelerator="Ctrl+D",
                command=self.duplicate_line,
            )
            menu.add_command(
                label="현재 줄 삭제",
                accelerator="Ctrl+Shift+K",
                command=self.delete_line,
            )
            menu.add_command(label="들여쓰기", command=self.indent_selection)
            menu.add_command(label="내어쓰기", command=self.unindent_selection)

        menu.add_separator()
        FlintStyle.add_check_menu_item(
            menu,
            label="자동 줄 바꿈",
            variable=self._flint_wrap_var,
            command=self.toggle_wrap,
        )
        self._flint_context_menu = menu

        bindings = {
            "<Button-3>": self._show_context_menu,
            "<Control-f>": self.open_find,
            "<Control-F>": self.open_find,
            "<Control-g>": self.open_goto_line,
            "<Control-G>": self.open_goto_line,
            "<Control-a>": self._select_all,
            "<Control-A>": self._select_all,
            "<F3>": self.find_next,
            "<Shift-F3>": self.find_previous,
            "<Control-plus>": self.zoom_in,
            "<Control-equal>": self.zoom_in,
            "<Control-minus>": self.zoom_out,
            "<Control-0>": self.zoom_reset,
        }
        for sequence, callback in bindings.items():
            self.bind(sequence, callback, add="+")

        if not self._flint_read_only_tools:
            edit_bindings = {
                "<Control-z>": self.undo_edit,
                "<Control-Z>": self.undo_edit,
                "<Control-y>": self.redo_edit,
                "<Control-Y>": self.redo_edit,
                "<Control-d>": self.duplicate_line,
                "<Control-D>": self.duplicate_line,
                "<Control-Shift-k>": self.delete_line,
                "<Control-Shift-K>": self.delete_line,
                "<Control-s>": self._save,
                "<Control-S>": self._save,
            }
            for sequence, callback in edit_bindings.items():
                self.bind(sequence, callback, add="+")




# ------------------------------------------------------------------
# 기존 Text에 기능 장착 / 표준 편집 영역 생성
# ------------------------------------------------------------------

def attach_full_editor(text: tk.Text, *, owner=None, read_only=False,
                       before_mutation=None, on_save=None) -> FlintEditorTools:
    """기존 tk.Text에 전체 편집 기능을 연결한다. 같은 위젯에 중복 연결하지 않는다."""
    existing = getattr(text, "_flint_full_editor_tools", None)
    if existing is not None:
        # 재장착 시 생략한 콜백(None)은 기존 설정을 지우지 않는다.
        if before_mutation is not None:
            existing.set_before_mutation(before_mutation)
        if on_save is not None:
            existing.set_save_callback(on_save)
        return existing
    tools = FlintEditorTools(text, owner=owner, read_only_tools=read_only,
                             before_mutation=before_mutation, on_save=on_save)
    text._flint_full_editor_tools = tools
    return tools


def mount_text_scrollbars(text: tk.Text, *, horizontal=False):
    """기존 tk.Text를 grid로 배치하고 자동 숨김 스크롤바를 연결한다."""
    parent = text.master
    y_scroll = ttk.Scrollbar(parent, orient="vertical", command=text.yview)
    x_scroll = ttk.Scrollbar(parent, orient="horizontal", command=text.xview) if horizontal else None
    text.configure(yscrollcommand=FlintStyle.auto_hide_scrollbar(y_scroll))
    if x_scroll is not None:
        text.configure(xscrollcommand=FlintStyle.auto_hide_scrollbar(x_scroll))
    text.grid(row=0, column=0, sticky="nsew")
    y_scroll.grid(row=0, column=1, sticky="ns")
    if x_scroll is not None:
        x_scroll.grid(row=1, column=0, sticky="ew")
    parent.rowconfigure(0, weight=1)
    parent.columnconfigure(0, weight=1)
    return y_scroll, x_scroll


def create_markdown_text(master, *, owner=None, **kwargs):
    defaults = dict(wrap="word", font=("Consolas", 11), undo=True, padx=14, pady=12,
                    background="#eef3f6", foreground="#25313a", insertbackground="#25313a",
                    selectbackground="#cddde7")
    defaults.update(kwargs)
    text = tk.Text(master, **defaults)
    attach_full_editor(text, owner=owner)
    return text


def create_css_text(master, *, owner=None, **kwargs):
    defaults = dict(wrap="none", font=("Consolas", 10), undo=True)
    defaults.update(kwargs)
    text = tk.Text(master, **defaults)
    attach_full_editor(text, owner=owner)
    return text


def create_text_viewer(master, *, owner=None, **kwargs):
    defaults = dict(wrap="word", font=("Malgun Gothic", 11), padx=20, pady=16,
                    relief="flat", borderwidth=0, cursor="arrow")
    defaults.update(kwargs)
    text = tk.Text(master, **defaults)
    attach_full_editor(text, owner=owner, read_only=True)
    return text

class FlintLogViewer:
    """Flint 공용 로그 보기 창. 실제 로그 파일을 읽고 내용을 비울 수 있다."""

    def __init__(
        self,
        owner: tk.Misc,
        log_path,
        *,
        title: str = "로그 보기",
        clear_text: str = "로그 지우기",
        empty_text: str = "로그가 없습니다.",
    ) -> None:
        from pathlib import Path

        self.owner = owner
        self.log_path = Path(log_path)
        self.title = title
        self.clear_text = clear_text
        self.empty_text = empty_text
        self.window: tk.Toplevel | None = None
        self.viewer: tk.Text | None = None

    def open(self):
        if self.window is not None:
            try:
                if self.window.winfo_exists():
                    self.refresh()
                    self.window.deiconify()
                    self.window.lift()
                    return self.window
            except tk.TclError:
                pass

        win = tk.Toplevel(self.owner)
        win.title(self.title)

        # 독립된 일반 Windows 창으로 사용한다.
        # transient를 쓰면 Windows에서 최소화/최대화 버튼이 빠질 수 있다.
        win.resizable(True, True)
        win.geometry("820x520")
        win.minsize(560, 320)
        self.window = win

        body = ttk.Frame(win, padding=10)
        body.pack(fill="both", expand=True)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        text_frame = ttk.Frame(body)
        text_frame.grid(row=0, column=0, sticky="nsew")
        viewer = create_text_viewer(text_frame, owner=win, wrap="none", font=("Consolas", 10))
        mount_text_scrollbars(viewer, horizontal=True)
        self.viewer = viewer

        controls = ttk.Frame(body)
        controls.grid(row=1, column=0, sticky="e", pady=(10, 0))
        FlintStyle.button(
            controls,
            text=self.clear_text,
            command=self.clear,
            kind="danger",
        ).pack(side="right")

        def close():
            self.window = None
            self.viewer = None
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", close)
        win.bind("<Escape>", lambda _event: close())
        self.refresh()
        return win

    def _set_text(self, value: str) -> None:
        if self.viewer is None:
            return
        self.viewer.configure(state="normal")
        self.viewer.delete("1.0", "end")
        if value:
            self.viewer.insert("1.0", value)
        self.viewer.configure(state="disabled")

    def refresh(self) -> None:
        try:
            value = self.log_path.read_text(encoding="utf-8") if self.log_path.exists() else ""
        except OSError as exc:
            value = f"{exc}"
        self._set_text(value or self.empty_text)

    def clear(self) -> None:
        """로그 파일은 유지하고 실제 내용을 0바이트로 비운다."""
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_path.write_text("", encoding="utf-8")
        except OSError as exc:
            self._set_text(f"{exc}")
            return
        self._set_text(self.empty_text)


def open_log_viewer(
    owner: tk.Misc,
    log_path,
    *,
    title: str = "로그 보기",
    clear_text: str = "로그 지우기",
    empty_text: str = "로그가 없습니다.",
) -> FlintLogViewer:
    """공용 Flint 로그 보기 창을 만들고 연다."""
    viewer = FlintLogViewer(
        owner,
        log_path,
        title=title,
        clear_text=clear_text,
        empty_text=empty_text,
    )
    viewer.open()
    return viewer

