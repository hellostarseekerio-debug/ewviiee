"""Builds a Windows .exe for the desktop GUI using PyInstaller.

Usage:
    python scripts/build_windows.py            # full build -> dist/OfficeAutomationPlatform.exe
    python scripts/build_windows.py --smoke-test  # validates PyInstaller + entrypoint import only

A full build must run on Windows (PyInstaller does not cross-compile).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENTRYPOINT = REPO_ROOT / "app" / "gui" / "main.py"


def smoke_test() -> None:
    """Verify PyInstaller is importable and the GUI entrypoint module parses,
    without invoking a full (slow) native build. Used by CI on every OS."""
    import importlib.util

    spec = importlib.util.find_spec("PyInstaller")
    if spec is None:
        print("PyInstaller not installed - run `pip install pyinstaller`", file=sys.stderr)
        raise SystemExit(1)
    compile(ENTRYPOINT.read_text(encoding="utf-8"), str(ENTRYPOINT), "exec")
    print("Smoke test passed: PyInstaller available, GUI entrypoint compiles.")


def full_build() -> None:
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--windowed",
            "--name",
            "OfficeAutomationPlatform",
            "--add-data",
            f"{REPO_ROOT / 'config'};config",
            str(ENTRYPOINT),
        ],
        cwd=REPO_ROOT,
    )
    print("Build complete: dist/OfficeAutomationPlatform/OfficeAutomationPlatform.exe")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()

    if args.smoke_test:
        smoke_test()
    else:
        full_build()


if __name__ == "__main__":
    main()
