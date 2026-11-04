#!/usr/bin/env python3
"""Static validation for the Windows packaging inputs (Task 8.4).

Checks WITHOUT building (no Windows, no PyInstaller, no Inno here):
  1. packaging/jarvis.spec parses as Python, its entry script exists, and
     every datas[] source file exists.
  2. packaging/jarvis.iss has the required sections and defines, and its
     [Files] Source points at the PyInstaller output dir.
  3. .github/workflows/release.yml is valid YAML with the expected jobs.

Exit 0 = all checks pass. This does NOT prove the installer works — the
first real build happens on Windows from the v1.0.0 tag (see
docs/PACKAGING.md).
"""

from __future__ import annotations

import ast
import os
import re

import yaml  # pyyaml ships with the dev venv; CI installs it too

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ERRORS: list[str] = []


def fail(msg: str) -> None:
    ERRORS.append(msg)
    print(f"FAIL: {msg}")


def check_spec() -> None:
    path = os.path.join(REPO, "packaging", "jarvis.spec")
    src = open(path, encoding="utf-8").read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        fail(f"jarvis.spec does not parse: {e}")
        return
    print("ok: jarvis.spec parses")
    # entry script = first positional arg of Analysis(...)
    entry = None
    datas = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Analysis":
            if node.args and isinstance(node.args[0], ast.List):
                elts = node.args[0].elts
                if elts and isinstance(elts[0], ast.Constant):
                    entry = elts[0].value
            for kw in node.keywords:
                if kw.arg == "datas" and isinstance(kw.value, ast.List):
                    for elt in kw.value.elts:
                        if isinstance(elt, ast.Tuple) and len(elt.elts) >= 1:
                            first = elt.elts[0]
                            if isinstance(first, ast.Constant):
                                datas.append(first.value)
    if entry:
        full = os.path.normpath(os.path.join(REPO, "packaging", entry))
        if os.path.exists(full):
            print(f"ok: entry script exists: {entry}")
        else:
            fail(f"entry script missing: {entry}")
    else:
        fail("could not find Analysis entry script")
    for d in datas:
        full = os.path.normpath(os.path.join(REPO, "packaging", d))
        # datas entries may be dirs; existence is what matters
        if os.path.exists(full):
            print(f"ok: datas source exists: {d}")
        else:
            fail(f"datas source missing: {d}")


def check_iss() -> None:
    path = os.path.join(REPO, "packaging", "jarvis.iss")
    src = open(path, encoding="utf-8").read()
    for section in ("[Setup]", "[Files]", "[Icons]"):
        if section in src:
            print(f"ok: iss section {section}")
        else:
            fail(f"iss missing section {section}")
    for define in ("MyAppName", "MyAppVersion", "MyAppPublisher", "MyAppURL"):
        if re.search(rf"#define\s+{define}\b", src):
            print(f"ok: iss define {define}")
        else:
            fail(f"iss missing #define {define}")
    if "PrivilegesRequired=lowest" in src:
        print("ok: per-user install (no admin)")
    else:
        fail("iss should install per-user (PrivilegesRequired=lowest)")
    m = re.search(r'Source:\s*"([^"]+)"', src)
    if m and "dist" in m.group(1):
        print(f"ok: [Files] Source points at PyInstaller output: {m.group(1)}")
    else:
        fail("[Files] Source does not reference the PyInstaller dist dir")


def check_release_workflow() -> None:
    path = os.path.join(REPO, ".github", "workflows", "release.yml")
    try:
        wf = yaml.safe_load(open(path, encoding="utf-8"))
    except Exception as e:
        fail(f"release.yml is not valid YAML: {e}")
        return
    print("ok: release.yml is valid YAML")
    jobs = wf.get("jobs") or {}
    if "build-windows" not in jobs:
        fail("release.yml missing build-windows job")
        return
    print("ok: build-windows job present")
    steps_text = str(jobs["build-windows"].get("steps", ""))
    for needle in ("pyinstaller", "ISCC", "gh release"):
        if needle.lower() in steps_text.lower():
            print(f"ok: release workflow mentions {needle}")
        else:
            fail(f"release workflow missing step for {needle}")


def main() -> int:
    check_spec()
    print()
    check_iss()
    print()
    check_release_workflow()
    print()
    if ERRORS:
        print(f"{len(ERRORS)} packaging check(s) FAILED")
        return 1
    print("all packaging checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
