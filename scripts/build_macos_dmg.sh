#!/usr/bin/env bash
# MathCoach macOS DMG：打包 .app，并附带 /Applications 软链接
set -euo pipefail

cd "$(dirname "$0")/.."

version=$(python -c "import mathcoach; print(mathcoach.__version__)")
app="dist/MathCoach.app"
if [ ! -d "$app" ]; then
  echo "缺少 $app，请先运行 python scripts/build_desktop.py" >&2
  exit 1
fi

staging=$(mktemp -d)
trap 'rm -rf "$staging"' EXIT

cp -R "$app" "$staging/"
ln -s /Applications "$staging/Applications"
mkdir -p dist/installer
hdiutil create -volname "MathCoach" -srcfolder "$staging" -ov -format UDZO "dist/installer/MathCoach-$version.dmg"
