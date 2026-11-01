"""FakeDesktop — in-memory fakes for every perception/control backend.

Lets Phase-5 modules run headless on Linux: the policy gate, audit,
privacy blocklist and ladder fallback logic all execute for real, only
the OS surface is fake. Use via :func:`install_fake_desktop` or the
``fake_desktop`` pytest fixture (defined in the test module).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from jarvis.perception import backends as B
from jarvis.perception.backends import ElementNode, WindowInfo


# ---------------------------------------------------------------------------
# Fake UIA
# ---------------------------------------------------------------------------

class FakeUIA(B.UIABackend):
    """In-memory window/element tree."""

    def __init__(self) -> None:
        self.windows: Dict[int, WindowInfo] = {}
        self.trees: Dict[int, ElementNode] = {}
        self.by_id: Dict[str, ElementNode] = {}
        self.invoked: List[str] = []
        self.text_set: Dict[str, str] = {}
        self._next = 1  # matches FakeContext's default active-window handle

    def add_window(self, title: str, process: str = "app.exe",
                   children: Optional[List[ElementNode]] = None) -> int:
        handle = self._next
        self._next += 1
        self.windows[handle] = WindowInfo(handle=handle, title=title,
                                          process=process)
        root = ElementNode(element_id=f"w{handle}", role="window", name=title,
                           children=children or [])
        self.trees[handle] = root
        self._index(root)
        return handle

    def _index(self, node: ElementNode) -> None:
        self.by_id[node.element_id] = node
        for child in node.children:
            self._index(child)

    def add_element(self, handle: int, parent_id: str,
                    role: str, name: str,
                    automation_id: str = "") -> ElementNode:
        el = ElementNode(
            element_id=f"e{len(self.by_id)}", role=role, name=name,
            automation_id=automation_id,
            bounds=(10, 10, 80, 24))
        parent = self.by_id[parent_id]
        parent.children.append(el)
        self.by_id[el.element_id] = el
        return el

    # -- protocol --
    def list_windows(self) -> List[WindowInfo]:
        return list(self.windows.values())

    def get_tree(self, handle: int, depth: int = 3) -> ElementNode:
        return self.trees[handle]

    def find(self, handle: int, name: Optional[str] = None,
             role: Optional[str] = None,
             automation_id: Optional[str] = None) -> Optional[ElementNode]:
        for el in self.by_id.values():
            if name and name.lower() not in el.name.lower():
                continue
            if role and role.lower() != el.role.lower():
                continue
            if automation_id and automation_id != el.automation_id:
                continue
            return el
        return None

    def invoke(self, element_id: str) -> bool:
        if element_id not in self.by_id:
            return False
        self.invoked.append(element_id)
        return True

    def get_text(self, element_id: str) -> str:
        if element_id in self.text_set:
            return self.text_set[element_id]
        el = self.by_id.get(element_id)
        return el.name if el else ""

    def set_text(self, element_id: str, value: str) -> bool:
        if element_id not in self.by_id:
            return False
        self.text_set[element_id] = value
        return True


# ---------------------------------------------------------------------------
# Fake screen + OCR
# ---------------------------------------------------------------------------

class FakeScreen(B.ScreenBackend):
    def __init__(self) -> None:
        self.captures: List[Tuple[str, tuple]] = []

    def capture_window(self, handle: int) -> bytes:
        self.captures.append(("window", (handle,)))
        return b"\x89PNG-fake-window-" + str(handle).encode()

    def capture_region(self, x: int, y: int, w: int, h: int) -> bytes:
        self.captures.append(("region", (x, y, w, h)))
        return b"\x89PNG-fake-region"


class FakeOCR(B.OCRBackend):
    def __init__(self, text: str = "fake ocr text") -> None:
        self.text = text
        self.calls: List[Tuple[bytes, str]] = []

    def read_text(self, image_png: bytes, lang: str = "en") -> str:
        self.calls.append((image_png, lang))
        return self.text


# ---------------------------------------------------------------------------
# Fake browser
# ---------------------------------------------------------------------------

@dataclass
class FakePage:
    url: str
    title: str
    ax_tree: str                      # accessibility snapshot text
    refs: Dict[str, str] = field(default_factory=dict)  # ref -> description


class FakeBrowser(B.BrowserBackend):
    """In-memory DOM automation."""

    def __init__(self, pages: Optional[Dict[str, FakePage]] = None) -> None:
        self.pages = pages or {}
        self._url = ""
        self.actions: List[Tuple[str, tuple]] = []

    def add_page(self, page: FakePage) -> None:
        self.pages[page.url] = page

    def open(self, url: str) -> str:
        self.actions.append(("open", (url,)))
        page = self.pages.get(url)
        if page is None:
            return f"404: no such fake page {url}"
        self._url = url
        return f"opened {page.title}"

    def snapshot(self) -> str:
        page = self.pages.get(self._url)
        return page.ax_tree if page else "(blank)"

    def click(self, ref: str) -> str:
        self.actions.append(("click", (ref,)))
        return f"clicked {ref}"

    def fill(self, ref: str, value: str) -> str:
        self.actions.append(("fill", (ref, value)))
        return f"filled {ref}"

    def submit(self, ref: Optional[str] = None) -> str:
        self.actions.append(("submit", (ref,)))
        return "submitted"

    @property
    def current_url(self) -> str:
        return self._url


# ---------------------------------------------------------------------------
# Fake VLM
# ---------------------------------------------------------------------------

class FakeVLM(B.VLMBackend):
    def __init__(self, pick: int = 1) -> None:
        self.pick = pick
        self.calls: List[Tuple[bytes, str, int]] = []

    def pick_element(self, image_png: bytes, prompt: str,
                     max_marks: int = 12) -> int:
        self.calls.append((image_png, prompt, max_marks))
        return self.pick


# ---------------------------------------------------------------------------
# Fake context + apps
# ---------------------------------------------------------------------------

class FakeContext(B.ContextBackend):
    def __init__(self, title: str = "Untitled - Notepad",
                 process: str = "notepad.exe",
                 selection: str = "", clipboard: bool = False,
                 clipboard_text: str = "") -> None:
        self._win = WindowInfo(handle=1, title=title, process=process)
        self._selection = selection
        self._clipboard = clipboard
        self._clipboard_text = clipboard_text

    def active_window(self) -> WindowInfo:
        return self._win

    def selected_text(self) -> str:
        return self._selection

    def clipboard_has_text(self) -> bool:
        return self._clipboard

    def clipboard_text(self) -> str:
        return self._clipboard_text


class FakeApps:
    """Records adapter calls; doubles as VSCode/Office/Spotify backends."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, tuple]] = []

    # VSCodeBackend
    def open_path(self, path: str) -> str:
        self.calls.append(("vscode.open_path", (path,)))
        return f"opened {path} in VS Code"

    def run_task(self, task: str, folder: str) -> str:
        self.calls.append(("vscode.run_task", (task, folder)))
        return f"ran task {task}"

    # OfficeBackend
    def open_document(self, path: str) -> str:
        self.calls.append(("office.open_document", (path,)))
        return f"opened {path}"

    def read_cells(self, path: str, sheet: str = "",
                   cell_range: str = "") -> str:
        self.calls.append(("office.read_cells", (path, sheet, cell_range)))
        return "A1: fake"

    def save_document(self, path: str) -> str:
        self.calls.append(("office.save_document", (path,)))
        return f"saved {path}"

    # SpotifyBackend
    def control(self, action: str, query: str = "") -> str:
        self.calls.append(("spotify.control", (action, query)))
        return f"spotify {action}"


# ---------------------------------------------------------------------------
# Installer
# ---------------------------------------------------------------------------

def install_fake_desktop(**overrides) -> Dict[str, object]:
    """Register a full fake desktop; returns the backend objects.

    Keyword overrides replace individual backends, e.g.
    ``install_fake_desktop(uia=my_uia)``.
    """
    made: Dict[str, object] = {
        "uia": FakeUIA(),
        "screen": FakeScreen(),
        "ocr": FakeOCR(),
        "browser": FakeBrowser(),
        "vlm": FakeVLM(),
        "context": FakeContext(),
        "apps": FakeApps(),
    }
    made.update(overrides)
    apps = made["apps"]
    B.set_backend("uia", made["uia"])
    B.set_backend("screen", made["screen"])
    B.set_backend("ocr", made["ocr"])
    B.set_backend("browser", made["browser"])
    B.set_backend("vlm", made["vlm"])
    B.set_backend("context", made["context"])
    B.set_backend("vscode", apps)
    B.set_backend("office", apps)
    B.set_backend("spotify", apps)
    return made


def uninstall_fake_desktop() -> None:
    B.clear_backends()
