#!/usr/bin/env bash
# Packages dist/OfficeAutomationPlatform.app into a distributable .dmg.
#
# Prerequisites:
#   1. Run `python scripts/build_macos.py` first to produce
#      dist/OfficeAutomationPlatform.app
#   2. Run this script on macOS (hdiutil is macOS-only)
#
# Usage:
#   bash packaging/macos/create_dmg.sh
#
# Output: dist/OfficeAutomationPlatform-0.1.0.dmg
#
# Code signing / notarization (required for Gatekeeper on a machine that
# isn't the one that built it) are NOT done by this script - they require
# an Apple Developer ID certificate, which is specific to your office's
# Apple Developer account. Once you have one:
#   codesign --deep --force --verify --verbose \
#       --sign "Developer ID Application: Your Office Name" \
#       dist/OfficeAutomationPlatform.app
#   xcrun notarytool submit dist/OfficeAutomationPlatform-0.1.0.dmg \
#       --apple-id you@example.gov.hk --team-id TEAMID --wait
#   xcrun stapler staple dist/OfficeAutomationPlatform-0.1.0.dmg
# See docs/INSTALLATION.md for the full checklist.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_PATH="$REPO_ROOT/dist/OfficeAutomationPlatform.app"
VERSION="0.1.0"
DMG_PATH="$REPO_ROOT/dist/OfficeAutomationPlatform-${VERSION}.dmg"
STAGING_DIR="$REPO_ROOT/dist/dmg_staging"

if [[ "$(uname)" != "Darwin" ]]; then
    echo "This script must run on macOS (uses hdiutil)." >&2
    exit 1
fi

if [[ ! -d "$APP_PATH" ]]; then
    echo "Error: $APP_PATH not found. Run 'python scripts/build_macos.py' first." >&2
    exit 1
fi

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"
cp -R "$APP_PATH" "$STAGING_DIR/"
ln -s /Applications "$STAGING_DIR/Applications"

rm -f "$DMG_PATH"
hdiutil create -volname "Office Automation Platform" \
    -srcfolder "$STAGING_DIR" \
    -ov -format UDZO \
    "$DMG_PATH"

rm -rf "$STAGING_DIR"
echo "Created $DMG_PATH"
echo "Reminder: this .dmg is unsigned. See this script's header comment for"
echo "code-signing/notarization steps required before distributing it to"
echo "machines other than the one that built it."
