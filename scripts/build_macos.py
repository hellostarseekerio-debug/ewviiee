"""Builds a macOS .app bundle for the desktop GUI using PyInstaller.

Usage:
    python scripts/build_macos.py               # full build -> dist/OfficeAutomationPlatform.app
    python scripts/build_macos.py --smoke-test   # validates PyInstaller + entrypoint import only

A full build must run on macOS (PyInstaller does not cross-compile), and
code signing/notarization for distribution outside your own machine
requires an Apple Developer certificate - see PyInstaller's macOS docs.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENTRYPOINT = REPO_ROOT / "app" / "gui" / "main.py"


def smoke_test() -> None:
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
            f"{REPO_ROOT / 'config'}:config",
            str(ENTRYPOINT),
        ],
        cwd=REPO_ROOT,
    )
    print("Build complete: dist/OfficeAutomationPlatform.app")
    print("Note: unsigned. For distribution, codesign + notarize with an Apple Developer ID.")


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
