#!/bin/bash
# EXCLUSIVAMENTE PARA O DESENVOLVEDOR/CI: o usuário final recebe apenas instalador .app no .dmg.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo 'Compilação macOS só é possível em um Mac compatível.' >&2; exit 2
fi
arch="$(uname -m)"
if [[ "$arch" != 'x86_64' && "$arch" != 'arm64' ]]; then
  echo "Arquitetura macOS não suportada: $arch" >&2; exit 2
fi
PY="$(command -v python3 || true)"
if [[ -z "$PY" ]]; then echo 'Python 3.12 é requerido SÓ PARA O BUILD.' >&2; exit 2; fi
"$PY" -m venv .venv
PY='.venv/bin/python'
"$PY" -m pip install -r requirements.txt pyinstaller pytest
"$PY" -m pytest -q
"$PY" -m PyInstaller --noconfirm --clean --onedir --windowed \
  --name OSReview --osx-bundle-identifier com.osreview.diagnostics \
  --icon assets/osreview.icns --add-data 'assets/osreview.png:assets' \
  --add-data 'licenses/NOTICE-LIBREHARDWAREMONITOR.txt:licenses' \
  --add-data 'licenses/MPL-2.0.txt:licenses' run.py
if [[ ! -d 'dist/OSReview.app' ]]; then echo 'OSReview.app ausente.' >&2; exit 1; fi

mkdir -p release
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
installer="$stage/Instalar OSReview.app"
mkdir -p "$installer/Contents/MacOS" "$installer/Contents/Resources"
cp installer/macos/NativeInstaller/Info.plist "$installer/Contents/Info.plist"
cp assets/osreview.icns "$installer/Contents/Resources/osreview.icns"
/usr/bin/ditto 'dist/OSReview.app' "$installer/Contents/Resources/OSReview.app"
/usr/bin/xcrun swiftc -O -parse-as-library -framework AppKit installer/macos/NativeInstaller/main.swift \
  -o "$installer/Contents/MacOS/InstalarOSReview"
chmod +x "$installer/Contents/MacOS/InstalarOSReview"

# Optional publisher signing in build environment. No ad-hoc identity is presented as trusted.
# Notarization and stapling must still be completed by the publisher before public release.
if [[ -n "${OSREVIEW_APPLE_DEVELOPER_ID:-}" ]]; then
  /usr/bin/codesign --force --deep --options runtime --timestamp \
    --sign "$OSREVIEW_APPLE_DEVELOPER_ID" "$installer/Contents/Resources/OSReview.app"
  /usr/bin/codesign --force --options runtime --timestamp \
    --sign "$OSREVIEW_APPLE_DEVELOPER_ID" "$installer"
  /usr/bin/codesign --verify --verbose=2 --deep --strict "$installer"
fi

cp installer/macos/README_MAC.txt "$stage/LEIA-ME.txt"
output="release/OSReview-0.9.1-rc.2-macOS-${arch}-NAO-NOTARIZADO.dmg"
hdiutil create -volname 'OSReview 0.9.1 RC2' -srcfolder "$stage" -ov -format UDZO "$output"
shasum -a 256 "$output" > "$output.sha256"
echo "DMG gerado: $output"
echo 'O usuário instala por interface gráfica, sem .command, Terminal, Python ou .NET.'
echo 'Antes de distribuir, assine e notarize com credenciais legítimas da Apple.'
