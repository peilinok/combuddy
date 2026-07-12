#!/usr/bin/env bash
set -euo pipefail

APP_PATH="${1:-dist/combuddy.app}"
DMG_PATH="${2:-dist/combuddy-macos-arm64.dmg}"
VOLUME_NAME="combuddy"

if [ ! -d "$APP_PATH" ]; then
  echo "missing app bundle: $APP_PATH" >&2
  exit 1
fi

HDIUTIL_INFO="$(hdiutil info)"
if grep -Eq "/Volumes/${VOLUME_NAME}( [0-9]+)?$" <<<"$HDIUTIL_INFO"; then
  echo "a ${VOLUME_NAME} disk image is already mounted; eject it before packaging" >&2
  exit 1
fi

mkdir -p "$(dirname "$DMG_PATH")"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/combuddy-dmg.XXXXXX")"
STAGING_DIR="$WORK_DIR/stage"
MOUNT_DIR="$WORK_DIR/mount"
RW_DMG="$WORK_DIR/combuddy-rw.dmg"
MOUNTED=0
mkdir "$STAGING_DIR" "$MOUNT_DIR"

cleanup() {
  if [ "$MOUNTED" -eq 1 ]; then
    hdiutil detach "$MOUNT_DIR" -quiet >/dev/null 2>&1 || true
  fi
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

ditto "$APP_PATH" "$STAGING_DIR/combuddy.app"
ln -s /Applications "$STAGING_DIR/Applications"

hdiutil create \
  -volname "$VOLUME_NAME" \
  -srcfolder "$STAGING_DIR" \
  -fs HFS+ \
  -fsargs "-c c=64,a=16,e=16" \
  -format UDRW \
  -ov \
  "$RW_DMG"

hdiutil attach "$RW_DMG" -mountpoint "$MOUNT_DIR" -nobrowse -quiet
MOUNTED=1

osascript <<APPLESCRIPT
tell application "Finder"
  set dmgFolder to POSIX file "$MOUNT_DIR" as alias
  open dmgFolder
  set current view of container window of dmgFolder to icon view
  try
    set toolbar visible of container window of dmgFolder to false
  end try
  try
    set statusbar visible of container window of dmgFolder to false
  end try
  set the bounds of container window of dmgFolder to {120, 120, 900, 560}
  set icon size of the icon view options of container window of dmgFolder to 128
  set arrangement of the icon view options of container window of dmgFolder to not arranged
  set position of item "combuddy.app" of container window of dmgFolder to {220, 220}
  set position of item "Applications" of container window of dmgFolder to {560, 220}
  close container window of dmgFolder
end tell
APPLESCRIPT

sync
hdiutil detach "$MOUNT_DIR" -quiet
MOUNTED=0

hdiutil convert "$RW_DMG" -format UDZO -imagekey zlib-level=9 -o "$DMG_PATH" -ov
