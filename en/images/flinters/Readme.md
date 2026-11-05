# Flinters

**Flinters**는 Flint 계열 Python 데스크톱 프로그램에서 공통으로 사용하는 GUI 및 작업 지원 모듈 모음입니다. `tkinter`/`ttk` 기반의 화면 구성, 텍스트 편집, Markdown 표시, 드래그 정렬, 진행 상태 표시 등을 재사용할 수 있도록 분리했습니다.

> Flinters는 단독 실행 프로그램이 아닌 **Python 패키지**입니다. 각 프로그램에서 필요한 모듈을 가져와 사용합니다.

## 주요 기능

| 모듈 | 역할 |
| --- | --- |
| `flinters.gui` | Flint 공통 테마와 GUI 위젯·메뉴·창·스크롤·선택 상태 관리 |
| `flinters.editor` | `tk.Text` 편집 기능 및 로그 뷰어 |
| `flinters.markdown` | Markdown을 HTML로 변환하고 Tk 기반으로 표시 |
| `flinters.reorder` | 목록 항목의 세로·가로 드래그 정렬 |
| `flinters.restarter` | Windows 프로그램 외부 재시작 지원 |
| `flinters.tooltip` | 위젯 도움말 툴팁과 관리 기능 |
| `flinters.whatsup` | 작업 상태 메시지 및 진행 대화상자 |
| `flinters.idle` | 대상 저장소·Google Drive 작업 상태 확인 및 유휴 대기 지원 |

### GUI 스타일 (`gui/`)

`FlintStyle`은 테마(`FlintTheme`), 메뉴, 창, 위젯, 스크롤 기능을 통합해 제공하는 인터페이스입니다. 별도의 `FlintWindowState`, `FlintSelection`, `FlintNameColorEditor`, `FlintFileList`도 제공합니다.

### 텍스트 편집 (`editor.py`)

잘라내기·복사·붙여넣기, 실행 취소·다시 실행, 찾기·바꾸기, 줄 이동·복제·삭제, 들여쓰기, 대소문자 변경, 줄 바꿈, 글꼴 확대·축소, 저장 콜백, 우클릭 메뉴, 스크롤바 등을 지원합니다. 필요한 기능만 부착하거나 통합 편집기를 구성할 수 있습니다.

### Markdown (`markdown.py`)

`md_to_html()`을 통한 Markdown→HTML 변환과 `MarkdownRenderer`를 통한 표시 기능을 제공합니다. 로컬 Markdown 링크 처리 옵션도 포함합니다.

### 외부 재시작 (`restarter.py`)

`request_restart()`는 Windows에서 독립적인 재시작 도우미를 실행합니다. 호출한 프로그램은 저장·정리 작업을 마친 뒤 정상 종료해야 합니다. 도우미는 기존 프로세스가 종료될 때까지 기다렸다가 프로그램을 다시 실행합니다.

```python
from flinters.restarter import request_restart

request_restart()
# 호출한 프로그램에서 필요한 종료 처리를 진행합니다.
```

### 작업 상태 및 유휴 확인 (`whatsup.py`, `idle.py`)

`whatsup.py`는 작업 메시지, 진행 상태 및 프로그램 응답 감시를 지원합니다. `idle.py`는 대상 경로 검사, Google Drive 사용 중 여부 확인 및 유휴 상태 대기 기능을 제공합니다. 일부 동작은 Windows 환경에 의존합니다.

## 디렉터리 구조

```text
flinters/
├── editor.py          # 공통 텍스트 편집기·로그 뷰어
├── idle.py            # 저장소·Google Drive 유휴 확인
├── markdown.py        # Markdown 변환·표시
├── reorder.py         # 드래그 정렬
├── restarter.py       # Windows 외부 재시작
├── tooltip.py         # 툴팁
├── whatsup.py         # 진행·상태 알림
└── gui/
    ├── __init__.py    # FlintStyle 및 공개 API
    ├── style.py       # 테마·스타일
    ├── menu.py        # 메뉴 구성
    ├── window.py      # 창 관련 기능
    ├── widget.py      # 공통 위젯
    ├── scroll.py      # 스크롤 기능
    ├── state.py       # 창 상태
    ├── selection.py   # 선택 관리
    ├── namecolor.py   # 이름·색상 편집
    └── filelist.py    # 파일 목록 위젯
```

`__pycache__/`는 Python이 생성하는 바이트코드 캐시로, 소스 배포 시 제외할 수 있습니다.

## 사용 환경

- Python 3 (정확한 최소 버전은 별도 확인 필요)
- `tkinter`/`ttk` 사용 가능한 데스크톱 환경
- Windows 전용 API를 사용하는 기능(`idle.py` 일부)은 Windows에서 사용

별도 패키징 설정이나 의존성 목록이 제공되지 않아 최소 Python 버전과 전체 지원 플랫폼은 확정하지 않았습니다.

## 기본 사용 예시

프로젝트에서 `flinters` 디렉터리가 Python 모듈 검색 경로에 있도록 배치합니다.

```python
import tkinter as tk
from flinters.gui import FlintStyle
from flinters.editor import attach_context_menu, attach_find, attach_zoom

root = tk.Tk()
root.title("Flinters Example")
FlintStyle.apply(root)

text = tk.Text(root, undo=True)
text.pack(fill="both", expand=True)

attach_context_menu(text)
attach_find(text, owner=root)
attach_zoom(text)

root.mainloop()
```

Markdown을 HTML 문자열로 변환하는 예시:

```python
from flinters.markdown import md_to_html

html = md_to_html("# Hello Flinters\n\n**Markdown** example")
```

## 구성 및 배포 참고

- Flinters는 여러 Flint 프로그램에서 중복되는 코드를 공통화하기 위한 라이브러리입니다.
- 프로그램별로 필요한 모듈만 불러와 사용할 수 있습니다.
- `flinters.restarter`는 Windows용이며, 패키징할 때 정상적으로 import되는 모듈은 일반적으로 빌드에 포함됩니다. 실제 배포 빌드는 별도 확인이 필요합니다.
- 배포 시 `flinters/` 패키지와 실제 사용하는 하위 모듈이 함께 포함되어야 합니다.
- 이 문서는 제공된 소스의 정적 분석을 바탕으로 작성했으며, GUI 실행 및 플랫폼별 동작은 별도로 검증하지 않았습니다.
