#!/usr/bin/env bash
set -euo pipefail

APP_PATH="${1:-dist/combuddy.app}"
DMG_PATH="${2:-dist/combuddy-macos-arm64.dmg}"

if [ ! -d "$APP_PATH" ]; then
  echo "missing app bundle: $APP_PATH" >&2
  exit 1
fi

mkdir -p "$(dirname "$DMG_PATH")"
DMG_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/combuddy-dmg.XXXXXX")"
trap 'rm -rf "$DMG_ROOT"' EXIT

ditto "$APP_PATH" "$DMG_ROOT/combuddy.app"
ln -s /Applications "$DMG_ROOT/Applications"
hdiutil create -volname combuddy -srcfolder "$DMG_ROOT" -ov -format UDZO "$DMG_PATH"
