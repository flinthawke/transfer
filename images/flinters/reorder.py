from __future__ import annotations

from typing import Callable, Generic, Iterable, Sequence, TypeVar

from flinters.gui import tk, ttk

T = TypeVar("T", bound=tk.Widget)


class VerticalDragReorder(Generic[T]):
    """Tkinter/ttk용 고품질 세로 드래그 재정렬 엔진.

    pack()으로 세로 배치되는 Frame류 목록을 대상으로 한다.

    특징
    ----
    - threshold를 넘을 때만 실제 드래그 시작
    - 원본 아이템을 목록에서 실제로 분리
    - 원본 높이만큼의 placeholder가 삽입 위치를 실시간으로 표시
    - 포인터를 잡은 위치 그대로 유지하는 floating ghost
    - 목록 위/아래 가장자리 자동 스크롤(Canvas 선택)
    - 외부 프로그램의 선택/저장/인덱스 갱신 콜백 지원
    - bind 중복 방지, 안전한 unbind/cancel/destroy

    items에는 실제 list 객체를 전달해야 한다. 드롭이 완료되면 이 list 자체의
    순서가 바뀐다.
    """

    def __init__(
        self,
        *,
        root: tk.Misc,
        container: tk.Misc,
        items: list[T],
        on_reorder: Callable[[], None] | None = None,
        ghost_factory: Callable[[T, tk.Toplevel], None] | None = None,
        enabled: Callable[[], bool] | None = None,
        on_drag_start: Callable[[T], None] | None = None,
        on_drag_end: Callable[[T, bool], None] | None = None,
        on_reindex: Callable[[T, int], None] | None = None,
        placeholder_factory: Callable[[T, tk.Misc], tk.Widget] | None = None,
        scroll_widget: tk.Canvas | None = None,
        threshold: int = 6,
        ghost_alpha: float = 0.96,
        ghost_offset: tuple[int, int] = (0, 0),
        item_pack_kwargs: dict | None = None,
        cursor: str = "fleur",
        auto_scroll: bool = True,
        auto_scroll_margin: int = 42,
        auto_scroll_units: int = 2,
    ) -> None:
        self.root = root
        self.container = container
        self.items = items

        self.on_reorder = on_reorder
        self.ghost_factory = ghost_factory
        self.enabled = enabled
        self.on_drag_start = on_drag_start
        self.on_drag_end = on_drag_end
        self.on_reindex = on_reindex
        self.placeholder_factory = placeholder_factory
        self.scroll_widget = scroll_widget
        self.threshold = max(0, int(threshold))
        self.ghost_alpha = max(0.15, min(float(ghost_alpha), 1.0))
        self.ghost_offset_x, self.ghost_offset_y = ghost_offset
        self.cursor = cursor

        self.item_pack_kwargs = item_pack_kwargs or {"fill": "x", "pady": 4}
        # 예전 API와의 호환을 위해 받지만 기본 placeholder에는 표시선을 그리지 않는다.

        self.auto_scroll = bool(auto_scroll)
        self.auto_scroll_margin = max(8, int(auto_scroll_margin))
        self.auto_scroll_units = max(1, int(auto_scroll_units))

        self.dragged: T | None = None
        self.drag_moved = False
        self.drag_start_x_root = 0
        self.drag_start_y_root = 0
        self._grab_x = 0
        self._grab_y = 0
        self._origin_index: int | None = None
        self.target_index: int | None = None

        self.ghost: tk.Toplevel | None = None
        self.placeholder: tk.Widget | None = None
        self._placeholder_height = 1

        # 세로 리오더는 드래그 시작 시 실제 슬롯들이 차지하던 자리만 후보로 쓴다.
        # 좌표는 container 내부 기준으로 저장해 Canvas가 스크롤되어도 흔들리지 않는다.
        self._drag_slot_centers: list[float] = []
        self._drag_extent_top: float | None = None
        self._drag_extent_bottom: float | None = None

        self._cursor_widgets: list[tk.Widget] = []
        self._bound_handles: dict[T, list[tk.Widget]] = {}
        self._bound_callbacks: dict[T, list[tuple[tk.Widget, str, str]]] = {}
        self._destroyed = False

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    @property
    def is_dragging(self) -> bool:
        return self.dragged is not None and self.drag_moved

    def bind(
        self,
        item: T,
        handles: Iterable[tk.Widget] | None = None,
        *,
        cursor_widgets: Iterable[tk.Widget] | None = None,
    ) -> None:
        """아이템에 드래그 이벤트를 연결한다."""
        if self._destroyed:
            return

        self.unbind(item)
        drag_handles = list(handles or [item])
        self._bound_handles[item] = drag_handles
        callbacks: list[tuple[tk.Widget, str, str]] = []

        for widget in drag_handles:
            bindings = (
                ("<ButtonPress-1>", lambda event, target=item: self.start(target, event)),
                ("<B1-Motion>", lambda event, target=item: self.motion(target, event)),
                ("<ButtonRelease-1>", lambda event, target=item: self.end(target, event)),
            )
            for sequence, callback in bindings:
                try:
                    funcid = widget.bind(sequence, callback, add="+")
                except tk.TclError:
                    continue
                if funcid:
                    callbacks.append((widget, sequence, funcid))

        self._bound_callbacks[item] = callbacks
        if cursor_widgets is not None:
            setattr(item, "_drag_reorder_cursor_widgets", list(cursor_widgets))

    def unbind(self, item: T) -> None:
        """이 관리자가 추가한 바인딩만 제거한다."""
        if self.dragged is item:
            self.cancel()

        for widget, sequence, funcid in self._bound_callbacks.pop(item, []):
            try:
                widget.unbind(sequence, funcid)
            except tk.TclError:
                pass

        self._bound_handles.pop(item, None)
        if hasattr(item, "_drag_reorder_cursor_widgets"):
            try:
                delattr(item, "_drag_reorder_cursor_widgets")
            except (AttributeError, tk.TclError):
                pass

    def cancel(self) -> None:
        """현재 드래그를 취소하고 원래 순서를 복원한다."""
        item = self.dragged
        had_drag = self.drag_moved

        self._finish_visuals()
        self.dragged = None
        self.drag_moved = False
        self.target_index = None
        self._origin_index = None
        self._restore_cursors()
        self.repack()

        if item is not None and self.on_drag_end:
            self.on_drag_end(item, False)

    def destroy(self) -> None:
        """엔진을 완전히 해제한다."""
        if self._destroyed:
            return
        self.cancel()
        for item in list(self._bound_callbacks):
            self.unbind(item)
        self._destroyed = True

    def repack(self) -> None:
        """현재 items 순서대로 목록을 다시 배치한다."""
        self._destroy_placeholder()
        for item in self.items:
            try:
                item.pack_forget()
            except tk.TclError:
                pass

        for index, item in enumerate(self.items):
            if self.on_reindex:
                self.on_reindex(item, index)
            try:
                item.pack(**self.item_pack_kwargs)
            except tk.TclError:
                pass

        self._refresh_container()

    # ------------------------------------------------------------------
    # 이벤트
    # ------------------------------------------------------------------

    def start(self, item: T, event: tk.Event) -> None:
        if self._destroyed or item not in self.items:
            return
        if self.enabled is not None and not self.enabled():
            return

        self.dragged = item
        self.drag_moved = False
        self.drag_start_x_root = int(event.x_root)
        self.drag_start_y_root = int(event.y_root)
        self._grab_x = int(getattr(event, "x", 0))
        self._grab_y = int(getattr(event, "y", 0))
        self._origin_index = self.items.index(item)
        self.target_index = self._origin_index

    def motion(self, item: T, event: tk.Event) -> None:
        if self._destroyed or self.dragged is not item:
            return

        if not self.drag_moved:
            dx = int(event.x_root) - self.drag_start_x_root
            dy = int(event.y_root) - self.drag_start_y_root
            if (dx * dx + dy * dy) ** 0.5 < self.threshold:
                return
            self._begin_drag(item, event)

        self._move_ghost(event)
        self._auto_scroll(event)
        self._refresh_container()

        target = self._calculate_target_index(int(event.y_root), item)
        if target != self.target_index:
            self.target_index = target
            self._place_placeholder(item, target)

    def end(self, item: T, _event: tk.Event | None = None) -> None:
        if self._destroyed or self.dragged is not item:
            return

        did_drag = self.drag_moved
        target_index = self.target_index
        origin_index = self._origin_index

        self._finish_visuals()
        self.dragged = None
        self.drag_moved = False
        self.target_index = None
        self._origin_index = None
        self._restore_cursors()

        changed = False
        if did_drag and target_index is not None and item in self.items:
            self.items.remove(item)
            target_index = max(0, min(int(target_index), len(self.items)))
            self.items.insert(target_index, item)
            changed = origin_index != self.items.index(item)

        self.repack()

        if changed and self.on_reorder:
            self.on_reorder()
        if self.on_drag_end:
            self.on_drag_end(item, changed)

    # ------------------------------------------------------------------
    # 드래그 시작 / placeholder
    # ------------------------------------------------------------------

    def _begin_drag(self, item: T, event: tk.Event) -> None:
        self.drag_moved = True
        try:
            self.container.update_idletasks()
            item.update_idletasks()
        except tk.TclError:
            pass

        self._placeholder_height = max(1, item.winfo_height(), item.winfo_reqheight())

        # 존재하는 슬롯 자리만 드롭 후보로 인정한다.
        # 아래쪽의 넓은 빈 Canvas 영역은 애초에 리오더 자리가 아니다.
        self._drag_slot_centers = []
        tops: list[float] = []
        bottoms: list[float] = []
        try:
            container_root_y = float(self.container.winfo_rooty())
        except tk.TclError:
            container_root_y = 0.0

        for entry in self.items:
            try:
                top = float(entry.winfo_rooty()) - container_root_y
                height = float(max(1, entry.winfo_height(), entry.winfo_reqheight()))
            except tk.TclError:
                continue
            tops.append(top)
            bottoms.append(top + height)
            self._drag_slot_centers.append(top + height / 2.0)

        if tops and bottoms:
            self._drag_extent_top = min(tops)
            self._drag_extent_bottom = max(bottoms)
        else:
            self._drag_extent_top = None
            self._drag_extent_bottom = None

        self._create_placeholder(item)
        self._create_ghost(item, event)

        try:
            item.pack_forget()
        except tk.TclError:
            pass

        self._place_placeholder(item, self._origin_index or 0)
        self._set_drag_cursors(item)

        if self.on_drag_start:
            self.on_drag_start(item)

    def _create_placeholder(self, item: T) -> None:
        self._destroy_placeholder()

        if self.placeholder_factory is not None:
            placeholder = self.placeholder_factory(item, self.container)
        else:
            # 삽입 위치는 색상 표시선이 아니라 실제 아이템 높이만큼의
            # 빈 공간으로만 표현한다. 목록이 자연스럽게 벌어지므로
            # 별도의 파란선/테두리는 표시하지 않는다.
            try:
                bg = self.container.cget("background")
            except (tk.TclError, KeyError):
                bg = "#f0f0f0"

            placeholder = tk.Frame(
                self.container,
                height=self._placeholder_height,
                bg=bg,
                bd=0,
                highlightthickness=0,
            )
            placeholder.pack_propagate(False)

        self.placeholder = placeholder

    def _place_placeholder(self, dragged: T, target_index: int) -> None:
        if self.placeholder is None:
            return

        remaining = [entry for entry in self.items if entry is not dragged]
        target_index = max(0, min(target_index, len(remaining)))

        # pack 순서를 확실히 재구성한다. 아이템 수가 일반 GUI 목록 수준일 때
        # 가장 예측 가능하고 플랫폼 차이가 적다.
        try:
            self.placeholder.pack_forget()
        except tk.TclError:
            pass
        for entry in remaining:
            try:
                entry.pack_forget()
            except tk.TclError:
                pass

        for index in range(len(remaining) + 1):
            if index == target_index:
                self.placeholder.pack(**self.item_pack_kwargs)
            if index < len(remaining):
                remaining[index].pack(**self.item_pack_kwargs)

        self._refresh_container()

    def _calculate_target_index(self, pointer_y_root: int, dragged: T) -> int:
        remaining = [entry for entry in self.items if entry is not dragged]
        if not remaining:
            return 0

        # 드래그 시작 시 저장한 "실제 슬롯 자리"를 기준으로만 이동한다.
        # Canvas의 남는 빈 공간에서는 새 placeholder 자리를 만들지 않고
        # 직전 target을 그대로 유지한다.
        if self._drag_slot_centers and self._drag_extent_top is not None and self._drag_extent_bottom is not None:
            try:
                pointer = float(pointer_y_root) - float(self.container.winfo_rooty())
            except tk.TclError:
                pointer = float(pointer_y_root)

            if pointer < self._drag_extent_top or pointer > self._drag_extent_bottom:
                if self.target_index is not None:
                    return max(0, min(int(self.target_index), len(remaining)))
                if self._origin_index is not None:
                    return max(0, min(int(self._origin_index), len(remaining)))
                return 0

            # 가장 가까운 기존 슬롯 위치를 삽입 위치로 사용한다.
            # 결과 범위는 0..len(remaining) == 원래 슬롯 수-1 이다.
            nearest = min(
                range(len(self._drag_slot_centers)),
                key=lambda index: abs(pointer - self._drag_slot_centers[index]),
            )
            return max(0, min(int(nearest), len(remaining)))

        # 좌표 확보에 실패한 예외 상황에서는 기존 방식으로 안전하게 폴백한다.
        target = len(remaining)
        for index, entry in enumerate(remaining):
            try:
                middle = entry.winfo_rooty() + entry.winfo_height() / 2
            except tk.TclError:
                continue
            if pointer_y_root < middle:
                target = index
                break
        return target

    # ------------------------------------------------------------------
    # ghost
    # ------------------------------------------------------------------

    def _create_ghost(self, item: T, event: tk.Event) -> None:
        self._destroy_ghost()
        ghost = tk.Toplevel(self.root)
        ghost.overrideredirect(True)

        try:
            ghost.attributes("-topmost", True)
            ghost.attributes("-alpha", self.ghost_alpha)
        except tk.TclError:
            pass

        if self.ghost_factory is not None:
            self.ghost_factory(item, ghost)
        else:
            self._build_default_ghost(item, ghost)

        ghost.update_idletasks()
        width = max(1, item.winfo_width(), ghost.winfo_reqwidth())
        height = max(1, item.winfo_height(), ghost.winfo_reqheight())

        x = int(event.x_root) - self._grab_x + self.ghost_offset_x
        y = int(event.y_root) - self._grab_y + self.ghost_offset_y
        ghost.geometry(f"{width}x{height}+{x}+{y}")
        self.ghost = ghost

    def _build_default_ghost(self, item: T, ghost: tk.Toplevel) -> None:
        # 기본 고스트도 강제 강조색 테두리를 넣지 않는다.
        # 프로그램이 고유한 고스트 디자인을 원하면 ghost_factory로 꾸민다.
        body = ttk.Frame(ghost, padding=(10, 7))
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=self._default_ghost_text(item), anchor="w").pack(fill="both", expand=True)

    @staticmethod
    def _default_ghost_text(item: T) -> str:
        # Frame 자체에 text가 없으면 직계 자식 중 첫 Label의 text를 이용한다.
        try:
            text = item.cget("text")
            if text:
                return str(text)
        except (tk.TclError, KeyError):
            pass

        try:
            for child in item.winfo_children():
                try:
                    text = child.cget("text")
                except (tk.TclError, KeyError):
                    continue
                if text:
                    return str(text)
        except tk.TclError:
            pass
        return item.winfo_name()

    def _move_ghost(self, event: tk.Event) -> None:
        if self.ghost is None:
            return
        x = int(event.x_root) - self._grab_x + self.ghost_offset_x
        y = int(event.y_root) - self._grab_y + self.ghost_offset_y
        try:
            self.ghost.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass

    def _destroy_ghost(self) -> None:
        if self.ghost is None:
            return
        try:
            self.ghost.destroy()
        except tk.TclError:
            pass
        self.ghost = None

    # ------------------------------------------------------------------
    # 자동 스크롤
    # ------------------------------------------------------------------

    def _auto_scroll(self, event: tk.Event) -> None:
        canvas = self.scroll_widget
        if not self.auto_scroll or canvas is None:
            return

        try:
            first, last = canvas.yview()
            # 콘텐츠가 viewport 안에 전부 들어오면 자동 스크롤할 이유가 없다.
            if first <= 0.0 and last >= 1.0:
                return

            top = canvas.winfo_rooty()
            bottom = top + canvas.winfo_height()
            pointer = int(event.y_root)
            if pointer < top + self.auto_scroll_margin and first > 0.0:
                canvas.yview_scroll(-self.auto_scroll_units, "units")
            elif pointer > bottom - self.auto_scroll_margin and last < 1.0:
                canvas.yview_scroll(self.auto_scroll_units, "units")
        except tk.TclError:
            return

    # ------------------------------------------------------------------
    # 커서 / 정리
    # ------------------------------------------------------------------

    def _cursor_targets(self, item: T) -> Sequence[tk.Widget]:
        custom = getattr(item, "_drag_reorder_cursor_widgets", None)
        if custom is not None:
            return custom
        return self._bound_handles.get(item, [item])

    def _set_drag_cursors(self, item: T) -> None:
        self._cursor_widgets = []
        for widget in self._cursor_targets(item):
            try:
                widget.configure(cursor=self.cursor)
                self._cursor_widgets.append(widget)
            except tk.TclError:
                pass

    def _restore_cursors(self) -> None:
        for widget in self._cursor_widgets:
            try:
                widget.configure(cursor="")
            except tk.TclError:
                pass
        self._cursor_widgets = []

    def _destroy_placeholder(self) -> None:
        if self.placeholder is None:
            return
        try:
            self.placeholder.destroy()
        except tk.TclError:
            pass
        self.placeholder = None

    def _finish_visuals(self) -> None:
        self._destroy_ghost()
        self._destroy_placeholder()
        self._drag_slot_centers = []
        self._drag_extent_top = None
        self._drag_extent_bottom = None

    def _refresh_container(self) -> None:
        try:
            self.container.update_idletasks()
        except tk.TclError:
            pass


# 구버전에서 내부 클래스명을 직접 참조한 코드가 있어도 깨지지 않게 유지한다.
_VerticalDragReorder = VerticalDragReorder


__all__ = ["VerticalDragReorder", "_VerticalDragReorder"]


class HorizontalDragReorder(VerticalDragReorder[T]):
    """가로로 pack()된 위젯 목록용 드래그 재정렬 엔진.

    VerticalDragReorder와 같은 threshold/ghost/placeholder/콜백 품질을 유지하면서
    X축 기준으로 삽입 위치를 계산한다.
    """

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("item_pack_kwargs", {"side": "left", "padx": 2})
        kwargs.setdefault("auto_scroll", False)
        super().__init__(*args, **kwargs)
        self._placeholder_width = 1

    def repack(self) -> None:
        """현재 items 순서대로 가로 목록을 다시 배치한다."""
        self._destroy_placeholder()
        for item in self.items:
            try:
                item.pack_forget()
            except tk.TclError:
                pass

        for index, item in enumerate(self.items):
            if self.on_reindex:
                self.on_reindex(item, index)
            try:
                item.pack(**self.item_pack_kwargs)
            except tk.TclError:
                pass

        self._refresh_container()

    def _begin_drag(self, item: T, event: tk.Event) -> None:
        try:
            item.update_idletasks()
            self._placeholder_width = max(1, item.winfo_width(), item.winfo_reqwidth())
        except tk.TclError:
            self._placeholder_width = 1
        super()._begin_drag(item, event)

    def _create_placeholder(self, item: T) -> None:
        self._destroy_placeholder()

        if self.placeholder_factory is not None:
            placeholder = self.placeholder_factory(item, self.container)
        else:
            try:
                bg = self.container.cget("background")
            except (tk.TclError, KeyError):
                bg = "#f0f0f0"

            placeholder = tk.Frame(
                self.container,
                width=self._placeholder_width,
                height=self._placeholder_height,
                bg=bg,
                bd=0,
                highlightthickness=0,
            )
            placeholder.pack_propagate(False)

        self.placeholder = placeholder

    def _place_placeholder(self, dragged: T, target_index: int) -> None:
        if self.placeholder is None:
            return

        remaining = [entry for entry in self.items if entry is not dragged]
        target_index = max(0, min(target_index, len(remaining)))

        try:
            self.placeholder.pack_forget()
        except tk.TclError:
            pass
        for entry in remaining:
            try:
                entry.pack_forget()
            except tk.TclError:
                pass

        for index in range(len(remaining) + 1):
            if index == target_index:
                self.placeholder.pack(**self.item_pack_kwargs)
            if index < len(remaining):
                remaining[index].pack(**self.item_pack_kwargs)

        self._refresh_container()

    def _calculate_target_index(self, pointer_x_root: int, dragged: T) -> int:
        remaining = [entry for entry in self.items if entry is not dragged]
        target = len(remaining)

        for index, entry in enumerate(remaining):
            try:
                middle = entry.winfo_rootx() + entry.winfo_width() / 2
            except tk.TclError:
                continue
            if pointer_x_root < middle:
                target = index
                break

        return target

    def motion(self, item: T, event: tk.Event) -> None:
        if self._destroyed or self.dragged is not item:
            return

        if not self.drag_moved:
            dx = int(event.x_root) - self.drag_start_x_root
            dy = int(event.y_root) - self.drag_start_y_root
            if (dx * dx + dy * dy) ** 0.5 < self.threshold:
                return
            self._begin_drag(item, event)

        self._move_ghost(event)
        self._refresh_container()

        target = self._calculate_target_index(int(event.x_root), item)
        if target != self.target_index:
            self.target_index = target
            self._place_placeholder(item, target)


__all__ = [
    "VerticalDragReorder",
    "HorizontalDragReorder",
    "_VerticalDragReorder",
]
