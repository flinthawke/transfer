"""Flint 공용 Markdown 엔진 + Tkinter 렌더러.

Markdown → HTML 변환과 Tkinter 표시를 이 모듈에서 공통 관리한다.
외부 Markdown 패키지에 의존하지 않으며 앱별 링크/경로 정책만 콜백으로 주입한다.
"""
from __future__ import annotations

from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
import webbrowser
from typing import Callable

from flinters.gui import tk, tkfont


# ============================================================================
# Markdown → HTML 공용 변환 엔진
# ============================================================================
_INLINE_TOKEN_PREFIX = "\x00FLINTMD"


def _inline_markdown(text: str) -> str:
    """Markdown 인라인 문법을 안전한 HTML로 변환한다."""
    escaped = escape(str(text or ''), quote=False)
    tokens: list[str] = []

    def stash(html: str) -> str:
        tokens.append(html)
        return f'{_INLINE_TOKEN_PREFIX}{len(tokens) - 1}\x00'

    # 인라인 코드는 가장 먼저 보호한다.
    escaped = re.sub(
        r'`([^`\n]+)`',
        lambda m: stash(f'<code>{m.group(1)}</code>'),
        escaped,
    )

    # 이미지와 링크. 로컬 상대경로와 http(s) 모두 허용한다.
    escaped = re.sub(
        r'!\[([^\]\n]*)\]\(([^)\s]+)(?:\s+["\']([^"\']*)["\'])?\)',
        lambda m: stash(
            '<img src="{}" alt="{}"{}>'.format(
                escape(m.group(2), quote=True),
                escape(m.group(1), quote=True),
                f' title="{escape(m.group(3), quote=True)}"' if m.group(3) else '',
            )
        ),
        escaped,
    )
    escaped = re.sub(
        r'\[([^\]\n]+)\]\(([^)\s]+)(?:\s+["\']([^"\']*)["\'])?\)',
        lambda m: stash(
            '<a href="{}"{}>{}</a>'.format(
                escape(m.group(2), quote=True),
                f' title="{escape(m.group(3), quote=True)}"' if m.group(3) else '',
                m.group(1),
            )
        ),
        escaped,
    )

    escaped = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', escaped)
    escaped = re.sub(r'__(.+?)__', r'<strong>\1</strong>', escaped)
    escaped = re.sub(r'~~(.+?)~~', r'<del>\1</del>', escaped)
    escaped = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', escaped)
    escaped = re.sub(r'(?<!_)_([^_\n]+)_(?!_)', r'<em>\1</em>', escaped)

    for index, html in enumerate(tokens):
        escaped = escaped.replace(f'{_INLINE_TOKEN_PREFIX}{index}\x00', html)
    return escaped


def _split_table_row(line: str) -> list[str]:
    """간단한 GFM 표 행을 셀 단위로 분리한다."""
    value = line.strip()
    if value.startswith('|'):
        value = value[1:]
    if value.endswith('|'):
        value = value[:-1]
    # 이 공용 엔진은 \| 이스케이프를 보존한다.
    sentinel = '\x00FLINTPIPE\x00'
    value = value.replace(r'\|', sentinel)
    cells = [cell.strip().replace(sentinel, '|') for cell in value.split('|')]
    return cells


def _table_alignment(cell: str) -> str:
    value = cell.strip()
    left = value.startswith(':')
    right = value.endswith(':')
    if left and right:
        return 'center'
    if right:
        return 'right'
    return 'left'


def _is_table_separator(line: str) -> bool:
    cells = _split_table_row(line)
    return bool(cells) and all(re.fullmatch(r':?-{3,}:?', cell.strip()) for cell in cells)


def _list_item_match(line: str):
    return re.match(r'^(\s*)([-+*]|\d+[.)])\s+(.+)$', line)


def _render_list(lines: list[str], start: int) -> tuple[str, int]:
    """연속된 Markdown 목록을 중첩 구조를 유지해 HTML로 변환한다."""
    first = _list_item_match(lines[start])
    if not first:
        return '', start
    base_indent = len(first.group(1).expandtabs(4))
    ordered = first.group(2)[0].isdigit()
    tag = 'ol' if ordered else 'ul'
    parts = [f'<{tag}>']
    i = start

    while i < len(lines):
        match = _list_item_match(lines[i])
        if not match:
            break
        indent = len(match.group(1).expandtabs(4))
        current_ordered = match.group(2)[0].isdigit()
        if indent < base_indent or (indent == base_indent and current_ordered != ordered):
            break
        if indent > base_indent:
            nested, new_i = _render_list(lines, i)
            if nested and len(parts) > 1:
                parts[-1] = parts[-1][:-5] + nested + '</li>' if parts[-1].endswith('</li>') else parts[-1] + nested
                i = new_i
                continue
            break

        content = _inline_markdown(match.group(3).strip())
        i += 1
        continuation: list[str] = []
        while i < len(lines):
            nested_match = _list_item_match(lines[i])
            if nested_match:
                nested_indent = len(nested_match.group(1).expandtabs(4))
                if nested_indent > base_indent:
                    break
                if nested_indent <= base_indent:
                    break
            if not lines[i].strip():
                break
            raw_indent = len(lines[i]) - len(lines[i].lstrip(' '))
            if raw_indent > base_indent:
                continuation.append(lines[i].strip())
                i += 1
            else:
                break
        if continuation:
            content += '<br>' + '<br>'.join(_inline_markdown(x) for x in continuation)
        parts.append(f'<li>{content}</li>')

        # 바로 뒤 중첩 목록을 현재 li 안에 넣는다.
        if i < len(lines):
            nested_match = _list_item_match(lines[i])
            if nested_match and len(nested_match.group(1).expandtabs(4)) > base_indent:
                nested, new_i = _render_list(lines, i)
                if nested:
                    parts[-1] = parts[-1][:-5] + nested + '</li>'
                    i = new_i

    parts.append(f'</{tag}>')
    return ''.join(parts), i


def _convert_local_markdown_links(text: str) -> str:
    """로컬 .md 링크만 .html로 변환한다."""
    pattern = re.compile(
        r'(?P<prefix>!?\[[^\]\n]*\]\()'
        r'(?P<target>[^)\s]+)'
        r'(?P<title>\s+[\"\'][^\"\']*[\"\'])?'
        r'(?P<suffix>\))'
    )

    def replace(match: re.Match[str]) -> str:
        target = match.group('target')
        if (
            not target
            or target.startswith('#')
            or target.startswith('//')
            or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target)
        ):
            return match.group(0)

        path_part, sep, fragment = target.partition('#')
        path_only, qsep, query = path_part.partition('?')
        if not path_only.lower().endswith('.md'):
            return match.group(0)

        converted = path_only[:-3] + '.html'
        if qsep:
            converted += '?' + query
        if sep:
            converted += '#' + fragment

        return (
            match.group('prefix')
            + converted
            + (match.group('title') or '')
            + match.group('suffix')
        )

    return pattern.sub(replace, text)


def md_to_html(markdown_text: str, *, convert_md_links: bool = False) -> str:
    """외부 패키지 없이 Markdown을 HTML5 조각으로 변환한다.

    지원: 제목, 문단/nl2br, 굵게/기울임/취소선, 인라인 코드,
    링크/이미지, 인용문, 순서/비순서 목록과 중첩 목록, 수평선,
    fenced code, GFM 형식 표.
    """
    source = str(markdown_text or '')
    if convert_md_links:
        source = _convert_local_markdown_links(source)
    source = source.replace('\r\n', '\n').replace('\r', '\n').strip()
    if not source:
        return ''

    lines = source.split('\n')
    output: list[str] = []
    paragraph: list[str] = []
    i = 0

    def flush_paragraph() -> None:
        if paragraph:
            output.append('<p>' + '<br>\n'.join(_inline_markdown(line.strip()) for line in paragraph) + '</p>')
            paragraph.clear()

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        if not stripped:
            flush_paragraph()
            i += 1
            continue

        # fenced code block
        fence = re.match(r'^(```+|~~~+)\s*([A-Za-z0-9_+.-]*)\s*$', stripped)
        if fence:
            flush_paragraph()
            fence_token = fence.group(1)
            language = fence.group(2)
            i += 1
            code_lines: list[str] = []
            while i < len(lines) and not re.match(r'^' + re.escape(fence_token[0]) + r'{' + str(len(fence_token)) + r',}\s*$', lines[i].strip()):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            class_attr = f' class="language-{escape(language, quote=True)}"' if language else ''
            output.append(f'<pre><code{class_attr}>{escape(chr(10).join(code_lines), quote=False)}</code></pre>')
            continue

        # ATX heading
        heading = re.match(r'^(#{1,6})\s+(.+?)\s*#*$', stripped)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            output.append(f'<h{level}>{_inline_markdown(heading.group(2))}</h{level}>')
            i += 1
            continue

        # Setext heading
        if i + 1 < len(lines) and re.fullmatch(r'\s*(=+|-+)\s*', lines[i + 1]) and stripped:
            flush_paragraph()
            level = 1 if '=' in lines[i + 1] else 2
            output.append(f'<h{level}>{_inline_markdown(stripped)}</h{level}>')
            i += 2
            continue

        if re.fullmatch(r'(?:-{3,}|\*{3,}|_{3,})', stripped):
            flush_paragraph()
            output.append('<hr>')
            i += 1
            continue

        # GFM table
        if '|' in raw and i + 1 < len(lines) and _is_table_separator(lines[i + 1]):
            flush_paragraph()
            headers = _split_table_row(raw)
            separators = _split_table_row(lines[i + 1])
            aligns = [_table_alignment(cell) for cell in separators]
            i += 2
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].strip() and '|' in lines[i]:
                rows.append(_split_table_row(lines[i]))
                i += 1
            head_html = ''.join(
                f'<th style="text-align: {aligns[idx] if idx < len(aligns) else "left"}">{_inline_markdown(cell)}</th>'
                for idx, cell in enumerate(headers)
            )
            body_html = ''.join(
                '<tr>' + ''.join(
                    f'<td style="text-align: {aligns[idx] if idx < len(aligns) else "left"}">{_inline_markdown(cell)}</td>'
                    for idx, cell in enumerate(row)
                ) + '</tr>'
                for row in rows
            )
            output.append(f'<table><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>')
            continue

        # blockquote: 연속된 > 블록을 재귀 변환한다.
        if re.match(r'^>\s?', stripped):
            flush_paragraph()
            quoted: list[str] = []
            while i < len(lines):
                q = re.match(r'^\s*>\s?(.*)$', lines[i])
                if not q:
                    break
                quoted.append(q.group(1))
                i += 1
            output.append('<blockquote>' + md_to_html('\n'.join(quoted), convert_md_links=convert_md_links) + '</blockquote>')
            continue

        if _list_item_match(raw):
            flush_paragraph()
            list_html, i = _render_list(lines, i)
            output.append(list_html)
            continue

        paragraph.append(raw)
        i += 1

    flush_paragraph()
    return ''.join(output)


# ============================================================================
# HTML 조각 파서
# ============================================================================
class _HtmlTreeParser(HTMLParser):
    """HTML 조각을 Tkinter가 순회하기 쉬운 간단한 트리로 변환한다."""

    _VOID_TAGS = {'br', 'hr', 'img', 'meta', 'link', 'input', 'source', 'wbr'}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = {'tag': 'root', 'attrs': {}, 'children': []}
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs) -> None:
        node = {'tag': tag.lower(), 'attrs': dict(attrs), 'children': []}
        self.stack[-1]['children'].append(node)
        if tag.lower() not in self._VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        if self.stack[-1].get('tag') == tag.lower() and tag.lower() not in self._VOID_TAGS:
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        wanted = tag.lower()
        for pos in range(len(self.stack) - 1, 0, -1):
            if self.stack[pos].get('tag') == wanted:
                del self.stack[pos:]
                break

    def handle_data(self, data: str) -> None:
        if data:
            self.stack[-1]['children'].append(data)


# ============================================================================
# Tkinter Markdown 렌더러
# ============================================================================
class MarkdownRenderer:
    """Flint 공용 Markdown HTML 결과를 Tkinter Text 위젯에 렌더링한다."""

    def __init__(
        self,
        rendered: tk.Text,
        *,
        get_current_path: Callable[[], Path | None],
        open_markdown: Callable[[Path], None],
        open_file: Callable[[Path], None],
        resolve_local_link: Callable[[Path], Path] | None = None,
    ) -> None:
        self.rendered = rendered
        self.get_current_path = get_current_path
        self.open_markdown = open_markdown
        self.open_file = open_file
        self.resolve_local_link = resolve_local_link
        self._link_serial = 0
        self._widgets: list[tk.Widget] = []
        self._images: list[object] = []
        self._configure_tags()

    # ------------------------------------------------------------------------
    # 렌더링 스타일
    # ------------------------------------------------------------------------
    def _configure_tags(self) -> None:
        r = self.rendered
        r.tag_configure('h1', font=('Malgun Gothic', 22, 'bold'), spacing1=8, spacing3=10)
        r.tag_configure('h2', font=('Malgun Gothic', 17, 'bold'), spacing1=12, spacing3=8)
        r.tag_configure('h3', font=('Malgun Gothic', 14, 'bold'), spacing1=10, spacing3=6)
        r.tag_configure('h4', font=('Malgun Gothic', 12, 'bold'), spacing1=8, spacing3=5)
        r.tag_configure('h5', font=('Malgun Gothic', 11, 'bold'), spacing1=7, spacing3=4)
        r.tag_configure('h6', font=('Malgun Gothic', 10, 'bold'), spacing1=6, spacing3=4)
        r.tag_configure('body', font=('Malgun Gothic', 11), spacing1=2, spacing3=2)
        r.tag_configure('paragraph', spacing1=1, spacing3=9)
        r.tag_configure('strong', font=('Malgun Gothic', 11, 'bold'))
        r.tag_configure('em', font=('Malgun Gothic', 11, 'italic'))
        r.tag_configure('del', overstrike=True)
        r.tag_configure('inline_code', font=('Consolas', 10), background='#eef2f4', foreground='#34444f')
        r.tag_configure('link', foreground='#2c6fa2', underline=True)
        r.tag_configure('code', font=('Consolas', 10), background='#f3f6f8', lmargin1=12, lmargin2=12, spacing1=3, spacing3=3)
        r.tag_configure('quote', font=('Malgun Gothic', 11, 'italic'), lmargin1=18, lmargin2=18, spacing1=4, spacing3=4)
        r.tag_configure('rule', foreground='#aab5bc', justify='left', spacing1=8, spacing3=8)
        r.tag_configure('table', font=('Consolas', 10), background='#f7f9fa', foreground='#25313a', lmargin1=8, lmargin2=8, spacing1=1, spacing3=1)
        for level in range(1, 5):
            margin = 18 * level
            r.tag_configure(f'list{level}', lmargin1=margin, lmargin2=margin)

    # ------------------------------------------------------------------------
    # 렌더링 진입점
    # ------------------------------------------------------------------------
    def render(self, markdown_text: str, *, convert_md_links: bool = False) -> None:
        """Markdown을 공용 변환 엔진으로 HTML화한 뒤 렌더 뷰에 표시한다."""
        html_fragment = md_to_html(markdown_text, convert_md_links=convert_md_links)
        r = self.rendered
        r.configure(state='normal')
        self._clear_embedded_objects()
        r.delete('1.0', 'end')
        self._link_serial = 0

        parser = _HtmlTreeParser()
        try:
            parser.feed(html_fragment)
            parser.close()
            for child in parser.root['children']:
                self._render_block(child)
        except Exception as exc:
            r.delete('1.0', 'end')
            r.insert('end', f'렌더링 오류: {exc}', ('body', 'em'))

        r.configure(state='disabled')
        r.yview_moveto(0.0)

    def _clear_embedded_objects(self) -> None:
        for widget in self._widgets:
            try:
                widget.destroy()
            except tk.TclError:
                pass
        self._widgets.clear()
        self._images.clear()

    def _ensure_list_tag(self, level: int) -> str:
        level = max(1, level)
        name = f'list{level}'
        if name not in self.rendered.tag_names():
            margin = min(180, 18 * level)
            self.rendered.tag_configure(name, lmargin1=margin, lmargin2=margin)
        return name

    def _node_text(self, node) -> str:
        if isinstance(node, str):
            return node
        tag = node.get('tag', '')
        if tag == 'br':
            return '\n'
        if tag == 'img':
            attrs = node.get('attrs', {})
            return attrs.get('alt') or Path(attrs.get('src', '')).name
        return ''.join(self._node_text(child) for child in node.get('children', []))

    # ------------------------------------------------------------------------
    # 링크, 앵커 및 로컬 리소스
    # ------------------------------------------------------------------------
    def _resolve_local_target(self, target: str) -> Path | None:
        clean = target.split('#', 1)[0].split('?', 1)[0].strip('<>')
        if not clean:
            return None
        current_path = self.get_current_path()
        base = current_path.parent if current_path is not None else Path.cwd()
        try:
            return (base / clean).resolve()
        except (OSError, RuntimeError):
            return None

    def _open_rendered_link(self, target: str) -> str:
        target = target.strip()
        if not target:
            return 'break'
        if target.startswith('#'):
            try:
                self.rendered.see(f'anchor::{target[1:]}')
            except tk.TclError:
                pass
            return 'break'
        if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target):
            webbrowser.open(target)
            return 'break'

        local_path = self._resolve_local_target(target)
        if local_path is None:
            return 'break'
        open_path = local_path
        if self.resolve_local_link is not None:
            try:
                open_path = self.resolve_local_link(local_path)
            except (OSError, RuntimeError):
                open_path = local_path

        if open_path.suffix.lower() == '.md' and open_path.is_file():
            self.open_markdown(open_path)
            return 'break'
        if open_path.is_file():
            try:
                self.open_file(open_path)
            except OSError:
                pass
        return 'break'

    def _register_anchor(self, node) -> None:
        attrs = node.get('attrs', {})
        anchor = attrs.get('id') or (attrs.get('name') if node.get('tag') == 'a' else '')
        if anchor:
            try:
                self.rendered.mark_set(f'anchor::{anchor}', 'end-1c')
            except tk.TclError:
                pass

    # ------------------------------------------------------------------------
    # 이미지
    # ------------------------------------------------------------------------
    def _insert_local_image(self, node, tags: tuple[str, ...]) -> None:
        attrs = node.get('attrs', {})
        src = (attrs.get('src') or '').strip()
        alt = attrs.get('alt') or Path(src).name or 'image'
        if not src or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', src) or src.startswith('//'):
            self.rendered.insert('end', f'[이미지: {alt}]', tags + ('em',))
            return

        image_path = self._resolve_local_target(src)
        if image_path is None or not image_path.is_file():
            self.rendered.insert('end', f'[이미지 없음: {alt}]', tags + ('em',))
            return
        try:
            try:
                from PIL import Image, ImageTk
                with Image.open(image_path) as source_image:
                    image = source_image.copy()
                self.rendered.update_idletasks()
                max_width = max(180, self.rendered.winfo_width() - 70)
                max_height = 520
                if image.width > max_width or image.height > max_height:
                    image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(image)
            except ImportError:
                photo = tk.PhotoImage(file=str(image_path))
            self._images.append(photo)
            self.rendered.image_create('end', image=photo, padx=4, pady=4)
        except Exception:
            self.rendered.insert('end', f'[이미지: {alt}]', tags + ('em',))

    def _bind_link_tag(self, tag_name: str, target: str) -> None:
        r = self.rendered
        r.tag_bind(tag_name, '<Enter>', lambda _event: r.configure(cursor='hand2'))
        r.tag_bind(tag_name, '<Leave>', lambda _event: r.configure(cursor='arrow'))
        r.tag_bind(tag_name, '<Button-1>', lambda _event, href=target: self._open_rendered_link(href))

    # ------------------------------------------------------------------------
    # 인라인 요소
    # ------------------------------------------------------------------------
    def _render_inline(self, node, tags: tuple[str, ...] = ('body',)) -> None:
        if isinstance(node, str):
            self.rendered.insert('end', node, tags)
            return
        tag = node.get('tag', '')
        attrs = node.get('attrs', {})
        self._register_anchor(node)
        if tag in {'strong', 'b'}:
            child_tags = tags + ('strong',)
        elif tag in {'em', 'i'}:
            child_tags = tags + ('em',)
        elif tag == 'code':
            child_tags = tags + ('inline_code',)
        elif tag in {'del', 's', 'strike'}:
            child_tags = tags + ('del',)
        else:
            child_tags = tags
        if tag == 'br':
            self.rendered.insert('end', '\n', tags)
            return
        if tag == 'img':
            self._insert_local_image(node, tags)
            return
        if tag == 'a':
            href = (attrs.get('href') or '').strip()
            if href:
                self._link_serial += 1
                link_tag = f'link_{self._link_serial}'
                self._bind_link_tag(link_tag, href)
                child_tags = child_tags + ('link', link_tag)
        for child in node.get('children', []):
            self._render_inline(child, child_tags)

    # ------------------------------------------------------------------------
    # 표
    # ------------------------------------------------------------------------
    def _table_rows(self, node) -> list[list[dict]]:
        rows: list[list[dict]] = []
        def walk(entry) -> None:
            if isinstance(entry, str):
                return
            if entry.get('tag') == 'tr':
                cells = [child for child in entry.get('children', []) if not isinstance(child, str) and child.get('tag') in {'th', 'td'}]
                rows.append(cells)
                return
            for child in entry.get('children', []):
                walk(child)
        walk(node)
        return rows

    def _insert_html_table(self, node) -> None:
        rows = self._table_rows(node)
        if not rows:
            return
        column_count = max(len(row) for row in rows)
        self.rendered.update_idletasks()
        available = max(280, self.rendered.winfo_width() - 58)
        cell_width_px = max(90, available // max(1, column_count))
        wraplength = max(70, cell_width_px - 18)
        table_frame = tk.Frame(self.rendered, bg='#c8d0d5', bd=0, highlightthickness=0)
        self._widgets.append(table_frame)
        for row_index, row in enumerate(rows):
            for col_index in range(column_count):
                cell_node = row[col_index] if col_index < len(row) else None
                value = self._node_text(cell_node).strip() if cell_node is not None else ''
                is_header = bool(cell_node and cell_node.get('tag') == 'th')
                style_text = (cell_node or {}).get('attrs', {}).get('style', '') if cell_node else ''
                anchor = 'center' if 'text-align: center' in style_text else ('e' if 'text-align: right' in style_text else 'w')
                justify = 'center' if anchor == 'center' else ('right' if anchor == 'e' else 'left')
                cell = tk.Label(
                    table_frame, text=value, anchor=anchor, justify=justify,
                    font=('Malgun Gothic', 10, 'bold' if is_header else 'normal'),
                    bg='#eef3f6' if is_header else '#ffffff', fg='#25313a',
                    padx=8, pady=6, wraplength=wraplength, bd=0,
                )
                cell.grid(row=row_index, column=col_index, sticky='nsew',
                          padx=(1 if col_index == 0 else 0, 1),
                          pady=(1 if row_index == 0 else 0, 1))
                table_frame.columnconfigure(col_index, weight=1, uniform='md_table')
        self.rendered.window_create('end', window=table_frame, padx=4, pady=6)
        self.rendered.insert('end', '\n', 'body')

    def _render_list(self, node, level: int = 1, ordered: bool = False) -> None:
        list_tag = self._ensure_list_tag(level)
        try:
            number = int(node.get('attrs', {}).get('start', '1'))
        except (TypeError, ValueError):
            number = 1
        for child in node.get('children', []):
            if isinstance(child, str) or child.get('tag') != 'li':
                continue
            prefix = f'{number}. ' if ordered else '• '
            self.rendered.insert('end', prefix, ('body', list_tag))
            nested_lists = []
            for part in child.get('children', []):
                if not isinstance(part, str) and part.get('tag') in {'ul', 'ol'}:
                    nested_lists.append(part)
                elif not isinstance(part, str) and part.get('tag') == 'p':
                    for inline_child in part.get('children', []):
                        self._render_inline(inline_child, ('body', list_tag))
                else:
                    self._render_inline(part, ('body', list_tag))
            self.rendered.insert('end', '\n', ('body', list_tag))
            for nested in nested_lists:
                self._render_list(nested, level + 1, nested.get('tag') == 'ol')
            number += 1

    def _insert_rule(self) -> None:
        try:
            self.rendered.update_idletasks()
            widget_width = max(1, self.rendered.winfo_width())
            padx = int(float(self.rendered.cget('padx') or 0))
            usable_width = max(40, widget_width - (padx * 2) - 12)
            rule_font = tkfont.Font(font=self.rendered.cget('font'))
            char_width = max(1, rule_font.measure('─'))
            char_count = max(8, int((usable_width - char_width) / char_width))
        except (tk.TclError, ValueError):
            char_count = 40
        self.rendered.insert('end', ('─' * char_count) + '\n', 'rule')

    # ------------------------------------------------------------------------
    # 블록 요소
    # ------------------------------------------------------------------------
    def _render_block(self, node, quote_level: int = 0) -> None:
        if isinstance(node, str):
            if node.strip():
                self.rendered.insert('end', node, 'body')
            return
        tag = node.get('tag', '')
        self._register_anchor(node)
        if tag in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
            for child in node.get('children', []):
                self._render_inline(child, (tag,))
            self.rendered.insert('end', '\n', tag)
            return
        if tag == 'p':
            base = ('quote', 'paragraph') if quote_level else ('body', 'paragraph')
            for child in node.get('children', []):
                self._render_inline(child, base)
            self.rendered.insert('end', '\n', base)
            return
        if tag == 'blockquote':
            for child in node.get('children', []):
                self._render_block(child, quote_level + 1)
            return
        if tag == 'ul':
            self._render_list(node, 1, False)
            return
        if tag == 'ol':
            self._render_list(node, 1, True)
            return
        if tag == 'pre':
            self.rendered.insert('end', self._node_text(node).rstrip('\n') + '\n', 'code')
            return
        if tag == 'table':
            self._insert_html_table(node)
            return
        if tag == 'hr':
            self._insert_rule()
            return
        if tag == 'img':
            self._insert_local_image(node, ('body',))
            self.rendered.insert('end', '\n', 'body')
            return
        if tag == 'br':
            self.rendered.insert('end', '\n', 'body')
            return

        children = node.get('children', [])
        block_tags = {'h1','h2','h3','h4','h5','h6','p','blockquote','ul','ol','pre','table','hr','div','section','article'}
        has_block_child = any(not isinstance(child, str) and child.get('tag') in block_tags for child in children)
        if has_block_child:
            for child in children:
                self._render_block(child, quote_level)
        else:
            for child in children:
                self._render_inline(child, ('quote',) if quote_level else ('body',))
            if children:
                self.rendered.insert('end', '\n', 'quote' if quote_level else 'body')
