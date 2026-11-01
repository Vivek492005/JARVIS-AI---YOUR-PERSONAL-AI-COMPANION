"""ToolSpec registrations for Phase-5 perception/control tools.

Each task module exposes its specs; :func:`register_perception_tools`
registers them idempotently. Called from
:func:`jarvis.tools.actions._register_tools` so every new surface goes
through the single policy gate (``run_action``) like all other tools.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from jarvis.tools.registry import REGISTRY, Risk, ToolSpec, tool


def _reg(spec: ToolSpec) -> ToolSpec:
    if spec.name in REGISTRY:
        return REGISTRY[spec.name]
    return tool(spec)


# ---------------------------------------------------------------------------
# 5.2 UIA tools
# ---------------------------------------------------------------------------

class DescribeScreenParams(BaseModel):
    handle: Optional[int] = Field(
        default=None, description="Window handle; default = active window.")
    depth: int = Field(default=3, ge=1, le=6,
                       description="Tree depth for the compact dump.")


class UiaFindParams(BaseModel):
    name: Optional[str] = Field(default=None, description="Substring of the control name.")
    role: Optional[str] = Field(default=None, description="Control role, e.g. 'button'.")
    automation_id: Optional[str] = Field(default=None)
    handle: Optional[int] = Field(default=None, description="Window handle; default = active.")


class UiaInvokeParams(BaseModel):
    element_id: str = Field(..., min_length=1, description="Element id from describe_screen/uia_find.")


class UiaGetTextParams(BaseModel):
    element_id: str = Field(..., min_length=1)


class UiaSetTextParams(BaseModel):
    element_id: str = Field(..., min_length=1)
    value: str = Field(..., max_length=10000)


def _h_describe_screen(args: Dict[str, Any], _cb: Any, _nf: str) -> str:
    from jarvis.perception.uia import controller
    from jarvis.perception.privacy import SensitiveWindowError
    try:
        return controller().describe_screen(handle=args.get("handle"),
                                            depth=args.get("depth", 3))
    except SensitiveWindowError as e:
        return f"Blocked: {e}"


def _h_uia_find(args: Dict[str, Any], _cb: Any, _nf: str) -> str:
    from jarvis.perception.uia import controller
    from jarvis.perception.privacy import SensitiveWindowError
    try:
        el = controller().find(name=args.get("name"), role=args.get("role"),
                               automation_id=args.get("automation_id"),
                               handle=args.get("handle"))
    except SensitiveWindowError as e:
        return f"Blocked: {e}"
    if el is None:
        return "no matching element"
    return f"[{el.role}] '{el.name}' #{el.element_id}"


def _h_uia_invoke(args: Dict[str, Any], _cb: Any, _nf: str) -> str:
    from jarvis.perception.uia import controller
    return controller().invoke(args["element_id"])


def _h_uia_get_text(args: Dict[str, Any], _cb: Any, _nf: str) -> str:
    from jarvis.perception.uia import controller
    return controller().get_text(args["element_id"])


def _h_uia_set_text(args: Dict[str, Any], _cb: Any, _nf: str) -> str:
    from jarvis.perception.uia import controller
    return controller().set_text(args["element_id"], args["value"])


def _uia_specs() -> List[ToolSpec]:
    base_invoke = dict(description="Clicks/invokes a UI element by id. "
                                   "Destructive labels (Delete/Send/Pay/...) "
                                   "escalate to DESTRUCTIVE automatically.",
                       params=UiaInvokeParams, handler=_h_uia_invoke)
    return [
        ToolSpec(name="describe_screen", risk=Risk.READ,
                 description="Compact accessibility tree of the active window "
                             "(role, name, id). Refuses sensitive windows.",
                 params=DescribeScreenParams, handler=_h_describe_screen,
                 carries_external_data=True),
        ToolSpec(name="uia_find", risk=Risk.READ,
                 description="Find a UI control by name/role/automation_id.",
                 params=UiaFindParams, handler=_h_uia_find),
        ToolSpec(name="uia_invoke", risk=Risk.REVERSIBLE, **base_invoke),
        ToolSpec(name="uia_invoke.normal", risk=Risk.REVERSIBLE,
                 description="Invoke a non-destructive control.",
                 params=UiaInvokeParams, handler=_h_uia_invoke),
        ToolSpec(name="uia_invoke.destructive", risk=Risk.DESTRUCTIVE,
                 description="Invoke a destructive control (Delete/Send/Pay/...).",
                 params=UiaInvokeParams, handler=_h_uia_invoke),
        ToolSpec(name="uia_get_text", risk=Risk.READ,
                 description="Read text of a UI element.",
                 params=UiaGetTextParams, handler=_h_uia_get_text,
                 carries_external_data=True),
        ToolSpec(name="uia_set_text", risk=Risk.REVERSIBLE,
                 description="Type text into a UI element.",
                 params=UiaSetTextParams, handler=_h_uia_set_text),
    ]


# ---------------------------------------------------------------------------
# 5.3 Screen capture + OCR
# ---------------------------------------------------------------------------

class CaptureScreenParams(BaseModel):
    handle: Optional[int] = Field(default=None, description="Window handle; default = active window.")
    keep_on_disk: bool = Field(default=False, description="Also save to screenshots/ (auto-deleted after 24h).")


class ReadScreenTextParams(BaseModel):
    handle: Optional[int] = Field(default=None)
    lang: str = Field(default="en", description="OCR language hint, e.g. 'en', 'hi', 'hi+en'.")


def _h_capture_screen(args: Dict[str, Any], _cb: Any, _nf: str) -> str:
    from jarvis.perception.screen import ScreenCapture
    from jarvis.perception.privacy import SensitiveWindowError
    try:
        info = ScreenCapture().capture(handle=args.get("handle"),
                                       keep_on_disk=bool(args.get("keep_on_disk", False)))
    except SensitiveWindowError as e:
        return f"Blocked: {e}"
    return (f"captured '{info['window']}' as {info['shot_id']} "
            f"({info['bytes']} bytes)" +
            (f" saved to {info['on_disk']}" if info["on_disk"] else ""))


def _h_read_screen_text(args: Dict[str, Any], _cb: Any, _nf: str) -> str:
    from jarvis.perception.screen import ScreenCapture
    from jarvis.perception.privacy import SensitiveWindowError
    try:
        return ScreenCapture().read_text(handle=args.get("handle"),
                                         lang=args.get("lang", "en"))
    except SensitiveWindowError as e:
        return f"Blocked: {e}"


def _screen_specs() -> List[ToolSpec]:
    return [
        ToolSpec(name="capture_screen", risk=Risk.READ,
                 description="Screenshot the active window (memory only unless "
                             "keep_on_disk). Refuses sensitive windows.",
                 params=CaptureScreenParams, handler=_h_capture_screen),
        ToolSpec(name="read_screen_text", risk=Risk.READ,
                 description="OCR text of the active window (redacted). "
                             "Result is untrusted external data.",
                 params=ReadScreenTextParams, handler=_h_read_screen_text,
                 carries_external_data=True),
    ]


# ---------------------------------------------------------------------------
# 5.4 VLM fallback (set-of-marks)
# ---------------------------------------------------------------------------

class VlmClickParams(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=500,
                        description="What to click, e.g. 'the Save button'.")
    handle: Optional[int] = Field(default=None, description="Window handle; default = active.")


def _h_vlm_click(args: Dict[str, Any], _cb: Any, _nf: str) -> str:
    from jarvis.perception.vlm import HandoffRequired, VLMClicker
    from jarvis.perception.privacy import SensitiveWindowError
    try:
        return VLMClicker().click_target(args["prompt"],
                                         handle=args.get("handle"))
    except HandoffRequired as e:
        return str(e)
    except SensitiveWindowError as e:
        return f"Blocked: {e}"


def _vlm_specs() -> List[ToolSpec]:
    return [
        # DESTRUCTIVE: least reliable rung (1-star); always confirms at L1.
        ToolSpec(name="vlm_click", risk=Risk.DESTRUCTIVE,
                 description="Last-resort visual click: numbered boxes on "
                             "screenshot, VLM picks one. Hands off on "
                             "login/CAPTCHA/payment/2FA/UAC.",
                 params=VlmClickParams, handler=_h_vlm_click),
    ]


# ---------------------------------------------------------------------------
# 5.5 Browser automation
# ---------------------------------------------------------------------------

class BrowserOpenParams(BaseModel):
    url: str = Field(..., min_length=1, max_length=2000)


class BrowserRefParams(BaseModel):
    ref: str = Field(..., min_length=1, description="Element ref from browser_read.")


class BrowserFillParams(BaseModel):
    ref: str = Field(..., min_length=1)
    value: str = Field(..., max_length=10000)


class BrowserSubmitParams(BaseModel):
    ref: Optional[str] = Field(default=None, description="Form/submit-button ref.")


def _browser_ctl() -> Any:
    from jarvis.perception.browser import BrowserController
    return BrowserController()


def _h_browser_open(args: Dict[str, Any], _cb: Any, _nf: str) -> str:
    from jarvis.perception.browser import BrowserBlocked
    try:
        return _browser_ctl().open(args["url"])
    except BrowserBlocked as e:
        return f"Blocked: {e}"


def _h_browser_read(args: Dict[str, Any], _cb: Any, _nf: str) -> str:
    return _browser_ctl().read()


def _h_browser_click(args: Dict[str, Any], _cb: Any, _nf: str) -> str:
    return _browser_ctl().click(args["ref"])


def _h_browser_fill(args: Dict[str, Any], _cb: Any, _nf: str) -> str:
    return _browser_ctl().fill(args["ref"], args["value"])


def _h_browser_submit(args: Dict[str, Any], _cb: Any, _nf: str) -> str:
    return _browser_ctl().submit(args.get("ref"))


def _browser_specs() -> List[ToolSpec]:
    return [
        ToolSpec(name="browser_open", risk=Risk.REVERSIBLE,
                 description="Open a URL in the dedicated jarvis browser "
                             "profile. file:// and chrome:// blocked.",
                 params=BrowserOpenParams, handler=_h_browser_open),
        ToolSpec(name="browser_read", risk=Risk.READ,
                 description="Accessibility snapshot of the current page "
                             "(untrusted).",
                 params=BaseModel, handler=_h_browser_read,
                 carries_external_data=True),
        ToolSpec(name="browser_click", risk=Risk.REVERSIBLE,
                 description="Click an element ref from browser_read.",
                 params=BrowserRefParams, handler=_h_browser_click),
        ToolSpec(name="browser_fill", risk=Risk.REVERSIBLE,
                 description="Fill a field ref from browser_read.",
                 params=BrowserFillParams, handler=_h_browser_fill),
        ToolSpec(name="browser_submit", risk=Risk.DESTRUCTIVE,
                 description="Submit a form. Hands off on login/payment pages.",
                 params=BrowserSubmitParams, handler=_h_browser_submit),
    ]


# ---------------------------------------------------------------------------
# 5.6 File intelligence
# ---------------------------------------------------------------------------

class FindFilesParams(BaseModel):
    name: Optional[str] = Field(default=None, description="Filename substring.")
    ext: Optional[str] = Field(default=None, description="Extension, e.g. 'pdf'.")
    newer_than_days: Optional[float] = Field(default=None, ge=0)
    root: Optional[str] = Field(default=None, description="Subfolder; default = workspace root.")


class FilePathParams(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)


class MoveCopyParams(BaseModel):
    src: str = Field(..., min_length=1, max_length=500)
    dst: str = Field(..., min_length=1, max_length=500)


class OrganizeParams(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)
    dry_run: bool = Field(default=True, description="True = show plan only.")


def _files_mod():
    from jarvis.perception import files as f
    return f


def _h_find_files(args, _cb, _nf):
    f = _files_mod()
    try:
        hits = f.find_files(name=args.get("name"), ext=args.get("ext"),
                            newer_than_days=args.get("newer_than_days"),
                            root=args.get("root"))
    except f.ScopeError as e:
        return f"Blocked: {e}"
    if not hits:
        return "no files found"
    return "\n".join(hits[:20]) + (f"\n...({len(hits)} total)" if len(hits) > 20 else "")


def _h_read_file(args, _cb, _nf):
    f = _files_mod()
    try:
        return f.read_file(args["path"])
    except f.ScopeError as e:
        return f"Blocked: {e}"


def _h_summarize_file(args, _cb, _nf):
    f = _files_mod()
    try:
        return f.summarize_file(args["path"])
    except f.ScopeError as e:
        return f"Blocked: {e}"


def _h_move_file(args, _cb, _nf):
    f = _files_mod()
    try:
        return f.move_file(args["src"], args["dst"])
    except f.ScopeError as e:
        return f"Blocked: {e}"


def _h_copy_file(args, _cb, _nf):
    f = _files_mod()
    try:
        return f.copy_file(args["src"], args["dst"])
    except f.ScopeError as e:
        return f"Blocked: {e}"


def _h_organize_folder(args, _cb, _nf):
    f = _files_mod()
    try:
        return f.organize_folder(args["path"], dry_run=bool(args.get("dry_run", True)))
    except f.ScopeError as e:
        return f"Blocked: {e}"


def _h_delete_file(args, _cb, _nf):
    f = _files_mod()
    try:
        return f.delete_file(args["path"])
    except f.ScopeError as e:
        return f"Blocked: {e}"
    except RuntimeError as e:
        return f"Cannot delete safely: {e}"


def _file_specs() -> List[ToolSpec]:
    return [
        ToolSpec(name="find_files", risk=Risk.READ,
                 description="Search the Jarvis workspace by name/extension/age.",
                 params=FindFilesParams, handler=_h_find_files),
        ToolSpec(name="read_file", risk=Risk.READ,
                 description="Read a workspace file (txt/pdf/docx/xlsx). Untrusted.",
                 params=FilePathParams, handler=_h_read_file,
                 carries_external_data=True),
        ToolSpec(name="summarize_file", risk=Risk.READ,
                 description="Size/type/preview summary of a workspace file.",
                 params=FilePathParams, handler=_h_summarize_file),
        ToolSpec(name="move_file", risk=Risk.REVERSIBLE,
                 description="Move a file inside the workspace (undoable).",
                 params=MoveCopyParams, handler=_h_move_file),
        ToolSpec(name="copy_file", risk=Risk.REVERSIBLE,
                 description="Copy a file inside the workspace (undoable).",
                 params=MoveCopyParams, handler=_h_copy_file),
        ToolSpec(name="organize_folder", risk=Risk.DESTRUCTIVE,
                 description="Sort a folder into subfolders. Dry-run plan first; "
                             "execute only with dry_run=false (undoable).",
                 params=OrganizeParams, handler=_h_organize_folder),
        ToolSpec(name="delete_file", risk=Risk.DESTRUCTIVE,
                 description="Move a workspace file to the Recycle Bin. "
                             "Permanent delete is never offered.",
                 params=FilePathParams, handler=_h_delete_file),
    ]


# ---------------------------------------------------------------------------
# 5.7 App adapters
# ---------------------------------------------------------------------------

class VSCodeOpenParams(BaseModel):
    path: str = Field(..., min_length=1, max_length=500,
                      description="Folder or file to open in VS Code.")


class VSCodeTaskParams(BaseModel):
    task: str = Field(..., min_length=1, max_length=200)
    folder: str = Field(default="", max_length=500)


class OfficeOpenParams(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)


class OfficeReadParams(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)
    sheet: str = Field(default="", max_length=100)
    cell_range: str = Field(default="", max_length=50)


class SpotifyParams(BaseModel):
    action: str = Field(..., description="play|pause|skip|previous|queue")
    query: str = Field(default="", max_length=300)


class SettingsParams(BaseModel):
    name: str = Field(..., description="Allowlisted setting name.")


def _h_vscode_open(args, _cb, _nf):
    from jarvis.perception.apps import VSCodeAdapter
    return VSCodeAdapter().open_path(args["path"])


def _h_vscode_task(args, _cb, _nf):
    from jarvis.perception.apps import VSCodeAdapter
    return VSCodeAdapter().run_task(args["task"], args.get("folder", ""))


def _h_office_open(args, _cb, _nf):
    from jarvis.perception.apps import OfficeAdapter
    return OfficeAdapter().open_document(args["path"])


def _h_office_read(args, _cb, _nf):
    from jarvis.perception.apps import OfficeAdapter
    return OfficeAdapter().read(args["path"], args.get("sheet", ""),
                                args.get("cell_range", ""))


def _h_office_save(args, _cb, _nf):
    from jarvis.perception.apps import OfficeAdapter
    return OfficeAdapter().save(args["path"])


def _h_spotify(args, _cb, _nf):
    from jarvis.perception.apps import SpotifyAdapter
    return SpotifyAdapter().control(args["action"], args.get("query", ""))


def _h_system_settings(args, _cb, _nf):
    from jarvis.perception.apps import apply_setting
    return apply_setting(args["name"])


def _app_specs() -> List[ToolSpec]:
    return [
        ToolSpec(name="vscode_open", risk=Risk.REVERSIBLE,
                 description="Open a folder/file in VS Code.",
                 params=VSCodeOpenParams, handler=_h_vscode_open),
        ToolSpec(name="vscode_task", risk=Risk.REVERSIBLE,
                 description="Run a VS Code task in a folder.",
                 params=VSCodeTaskParams, handler=_h_vscode_task),
        ToolSpec(name="office_open", risk=Risk.REVERSIBLE,
                 description="Open a Word/Excel/PowerPoint document.",
                 params=OfficeOpenParams, handler=_h_office_open),
        ToolSpec(name="office_read", risk=Risk.READ,
                 description="Read cells/text from an Office document. Untrusted.",
                 params=OfficeReadParams, handler=_h_office_read,
                 carries_external_data=True),
        ToolSpec(name="office_save", risk=Risk.REVERSIBLE,
                 description="Save the open Office document.",
                 params=OfficeOpenParams, handler=_h_office_save),
        ToolSpec(name="spotify", risk=Risk.REVERSIBLE,
                 description="Spotify: play|pause|skip|previous|queue.",
                 params=SpotifyParams, handler=_h_spotify),
        ToolSpec(name="system_settings", risk=Risk.REVERSIBLE,
                 description="Allowlisted system settings only "
                             "(volume/brightness/wifi).",
                 params=SettingsParams, handler=_h_system_settings),
    ]


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

def register_perception_tools() -> None:
    """Idempotent registration of all Phase-5 tool specs."""
    for spec in (_uia_specs() + _screen_specs() + _vlm_specs()
                 + _browser_specs() + _file_specs() + _app_specs()):
        _reg(spec)
