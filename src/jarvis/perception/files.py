"""File intelligence (Master Plan Task 5.6).

Scoped workspace model (Windows agent-workspace style):
- Default root: ``~/JarvisWorkspace`` (overridable via ``JARVIS_WORKSPACE``
  env for tests). Extra approved dirs via ``files.approved_dirs`` setting.
- Every path is resolved and must stay inside an approved root —
  ``..`` traversal raises :class:`ScopeError`.
- **Safe delete:** :func:`delete_file` uses ``send2trash`` (Recycle Bin)
  only. There is deliberately NO permanent-delete tool.
- **Dry-run first:** :func:`organize_folder` returns a plan by default;
  execution needs ``dry_run=False`` (and the DESTRUCTIVE policy gate).
- Bulk operations push per-file inverses into a pending-undo list that
  the brain loop's :class:`UndoJournal` drains after execution, so
  "wapas kar do" replays them.

Tools: ``find_files`` / ``read_file`` / ``summarize_file`` (READ),
``move_file`` / ``copy_file`` (REVERSIBLE), ``organize_folder`` /
``delete_file`` (DESTRUCTIVE).
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ScopeError(PermissionError):
    """Path is outside the approved workspace."""


# ---------------------------------------------------------------------------
# Scoped workspace
# ---------------------------------------------------------------------------


def workspace_root() -> Path:
    override = os.environ.get("JARVIS_WORKSPACE")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / "JarvisWorkspace"


def approved_roots() -> List[Path]:
    roots = [workspace_root()]
    try:
        from jarvis.core.config import get_settings

        extra = getattr(get_settings().files, "approved_dirs", None) or []
        roots.extend(Path(e).expanduser().resolve() for e in extra)
    except Exception as e:
        logger.debug(
            "approved-dirs resolve best-effort failed: %s",
            e,
        )
    return roots


def resolve_scoped(path_str: str) -> Path:
    """Resolve ``path_str``; must stay inside an approved root.

    Raises :class:`ScopeError` on traversal or out-of-scope paths.
    """
    if not path_str or not path_str.strip():
        raise ScopeError("empty path")
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = workspace_root() / p
    p = p.resolve()
    for root in approved_roots():
        try:
            p.relative_to(root)
            return p
        except ValueError:
            continue
    raise ScopeError(f"path outside approved workspace: {path_str}")


# ---------------------------------------------------------------------------
# Undo support (drained by brain.loop.UndoJournal.record)
# ---------------------------------------------------------------------------

_PENDING_UNDO: List[Tuple[str, Dict[str, Any]]] = []


def record_pending_undo(tool: str, args: Dict[str, Any]) -> None:
    _PENDING_UNDO.append((tool, args))


def drain_pending_undo() -> List[Tuple[str, Dict[str, Any]]]:
    pending = list(_PENDING_UNDO)
    _PENDING_UNDO.clear()
    return pending


def inverse_of(tool: str, args: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Inverse file operation for the undo journal."""
    if tool == "move_file":
        src, dst = args.get("src", ""), args.get("dst", "")
        if src and dst:
            return ("move_file", {"src": dst, "dst": src})
    elif tool == "copy_file":
        dst = args.get("dst", "")
        if dst:
            return ("delete_file", {"path": dst})
    return None


# ---------------------------------------------------------------------------
# find / read / summarize
# ---------------------------------------------------------------------------

_FIND_TIME_CAP_S = 5.0
_FIND_MAX_RESULTS = 100


def find_files(
    name: Optional[str] = None,
    ext: Optional[str] = None,
    newer_than_days: Optional[float] = None,
    root: Optional[str] = None,
) -> List[str]:
    """Search the workspace (5 s cap, 100 results max)."""
    base = resolve_scoped(root) if root else workspace_root()
    if not base.is_dir():
        return []
    if ext and not ext.startswith("."):
        ext = "." + ext
    cutoff = time.time() - newer_than_days * 86400 if newer_than_days else 0
    start = time.time()
    hits: List[str] = []
    name_l = (name or "").lower()
    for dirpath, _dirnames, filenames in os.walk(base):
        if time.time() - start > _FIND_TIME_CAP_S:
            break
        for fn in filenames:
            if len(hits) >= _FIND_MAX_RESULTS:
                return hits
            if name_l and name_l not in fn.lower():
                continue
            if ext and not fn.lower().endswith(ext.lower()):
                continue
            full = Path(dirpath) / fn
            if cutoff and full.stat().st_mtime < cutoff:
                continue
            hits.append(str(full))
    return hits


_READ_MAX_CHARS = 20000

_TEXT_EXTS = {
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".log",
    ".py",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".xml",
    ".html",
}


def read_file(path: str, max_chars: int = _READ_MAX_CHARS) -> str:
    """Read a file as text. PDF/DOCX/XLSX via optional libs."""
    p = resolve_scoped(path)
    if not p.is_file():
        return f"not a file: {path}"
    suffix = p.suffix.lower()
    if suffix in _TEXT_EXTS or suffix == "":
        try:
            return p.read_text(encoding="utf-8", errors="replace")[:max_chars]
        except OSError as e:
            return f"could not read: {e}"
    if suffix == ".pdf":
        return _read_pdf(p, max_chars)
    if suffix == ".docx":
        return _read_docx(p, max_chars)
    if suffix in (".xlsx", ".xls"):
        return _read_xlsx(p, max_chars)
    return f"unsupported type {suffix}; text preview unavailable"


def _read_pdf(p: Path, max_chars: int) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "PDF support needs the 'pypdf' package (pip install pypdf)"
    try:
        reader = PdfReader(str(p))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return text[:max_chars] or "(no extractable text)"
    except Exception as e:
        return f"could not parse PDF: {e}"


def _read_docx(p: Path, max_chars: int) -> str:
    try:
        import docx
    except ImportError:
        return "DOCX support needs 'python-docx' (pip install python-docx)"
    try:
        doc = docx.Document(str(p))
        return "\n".join(p_.text for p_ in doc.paragraphs)[:max_chars]
    except Exception as e:
        return f"could not parse DOCX: {e}"


def _read_xlsx(p: Path, max_chars: int) -> str:
    try:
        import openpyxl
    except ImportError:
        return "XLSX support needs 'openpyxl' (pip install openpyxl)"
    try:
        wb = openpyxl.load_workbook(str(p), read_only=True, data_only=True)
        out = []
        for ws in wb.worksheets[:3]:
            out.append(f"== {ws.title} ==")
            for row in ws.iter_rows(min_row=1, max_row=20, values_only=True):
                out.append(" | ".join("" if v is None else str(v) for v in row))
        return "\n".join(out)[:max_chars]
    except Exception as e:
        return f"could not parse XLSX: {e}"


def summarize_file(path: str) -> str:
    """One-paragraph summary: size, type, peek."""
    p = resolve_scoped(path)
    if not p.is_file():
        return f"not a file: {path}"
    size = p.stat().st_size
    suffix = p.suffix.lower() or "(no extension)"
    peek = read_file(path, max_chars=2000)
    lines = peek.count("\n") + 1
    return (
        f"{p.name}: {size} bytes, type {suffix}, ~{lines} lines previewed.\n"
        f"--- preview ---\n{peek[:1200]}"
    )


# ---------------------------------------------------------------------------
# move / copy / delete (trash only)
# ---------------------------------------------------------------------------


def move_file(src: str, dst: str) -> str:
    s, d = resolve_scoped(src), resolve_scoped(dst)
    if not s.exists():
        return f"source not found: {src}"
    if d.is_dir():
        d = d / s.name
    d.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(s), str(d))
    return f"moved {s.name} -> {d}"


def copy_file(src: str, dst: str) -> str:
    s, d = resolve_scoped(src), resolve_scoped(dst)
    if not s.is_file():
        return f"source not a file: {src}"
    if d.is_dir():
        d = d / s.name
    d.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(s), str(d))
    return f"copied {s.name} -> {d}"


def delete_file(path: str) -> str:
    """Move to Recycle Bin via send2trash. Permanent delete is NOT offered."""
    p = resolve_scoped(path)
    if not p.exists():
        return f"not found: {path}"
    try:
        import send2trash
    except ImportError:
        raise RuntimeError("send2trash not installed (pip install send2trash)") from None
    send2trash.send2trash(str(p))
    return f"moved to Recycle Bin: {p.name}"


# ---------------------------------------------------------------------------
# organize_folder: dry-run plan first, execute on confirmation
# ---------------------------------------------------------------------------

_CATEGORIES = {
    "Documents": {".pdf", ".docx", ".doc", ".txt", ".md", ".rtf", ".odt"},
    "Images": {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"},
    "Audio": {".mp3", ".wav", ".ogg", ".flac", ".m4a"},
    "Video": {".mp4", ".mkv", ".avi", ".mov", ".webm"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Code": {".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs", ".html", ".css"},
    "Spreadsheets": {".xlsx", ".xls", ".csv"},
}


def _category_for(suffix: str) -> str:
    for cat, exts in _CATEGORIES.items():
        if suffix in exts:
            return cat
    return "Others"


def organize_folder(path: str, dry_run: bool = True) -> str:
    """Plan (dry_run=True) or execute organizing files into subfolders.

    Execution moves each file and records per-file inverses for undo.
    """
    folder = resolve_scoped(path)
    if not folder.is_dir():
        return f"not a folder: {path}"
    plan: Dict[str, List[str]] = {}
    for item in sorted(folder.iterdir()):
        if not item.is_file():
            continue
        cat = _category_for(item.suffix.lower())
        plan.setdefault(cat, []).append(item.name)
    if not plan:
        return "folder is empty; nothing to organize"
    total = sum(len(v) for v in plan.values())
    lines = [f"Plan: {total} files -> {len(plan)} folders in {folder}"]
    for cat in sorted(plan):
        lines.append(
            f"  {cat}/: {len(plan[cat])} files "
            f"({', '.join(plan[cat][:5])}"
            f"{'...' if len(plan[cat]) > 5 else ''})"
        )
    if dry_run:
        lines.append("Dry run only — pass dry_run=false to execute.")
        return "\n".join(lines)
    moved = 0
    for cat, names in plan.items():
        dest_dir = folder / cat
        dest_dir.mkdir(exist_ok=True)
        for name in names:
            src, dst = folder / name, dest_dir / name
            if dst.exists():
                continue  # never overwrite silently
            shutil.move(str(src), str(dst))
            record_pending_undo("move_file", {"src": str(dst), "dst": str(src)})
            moved += 1
    return f"organized {moved}/{total} files into {len(plan)} folders"
