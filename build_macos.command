#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ "$(uname -s)" != "Darwin" ]; then
  echo "Run this script on macOS." >&2
  exit 1
fi
build_python="${ASTRO_BUILD_PYTHON:-python3.12}"
if [ ! -x .build-venv/bin/python ]; then
  if ! command -v "$build_python" >/dev/null 2>&1 && [ ! -x "$build_python" ]; then
    echo "Python 3.12 not found. Install it or set ASTRO_BUILD_PYTHON to Python 3.11+." >&2
    exit 1
  fi
  "$build_python" -m venv .build-venv
fi
.build-venv/bin/python -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
.build-venv/bin/python -m pip install --upgrade pip
.build-venv/bin/python -m pip install -r requirements.txt -r packaging/requirements-build.txt
.build-venv/bin/python packaging/build_app.py
build_arch="$(.build-venv/bin/python -c 'import platform; print(platform.machine())')"
mkdir -p release build
stage_path="$(mktemp -d "$PWD/build/dmg-stage.XXXXXX")"
trap 'rm -rf "$stage_path"' EXIT
ditto dist/AstroLaboratory.app "$stage_path/AstroLaboratory.app"
ln -s /Applications "$stage_path/Applications"
cat > "$stage_path/Install.txt" <<'EOF'
Drag AstroLaboratory.app to Applications, then open it.
Your default browser opens the local interface.
Use Quit in the app's web interface to stop the local server.
GraXpert and RC-Astro must be installed and licensed separately.
EOF
dmg_path="$PWD/release/AstroLaboratory-0.8.0-macOS-$build_arch.dmg"
if [ -f "$dmg_path" ]; then
  mv "$dmg_path" "$dmg_path.previous-$(date +%Y%m%d-%H%M%S)"
fi
hdiutil create -volname "Astro Laboratory" -srcfolder "$stage_path" -ov -format UDZO "$dmg_path"
if [ -n "${CODESIGN_IDENTITY:-}" ]; then
  codesign --force --sign "$CODESIGN_IDENTITY" "$dmg_path"
fi
if [ -n "${NOTARY_PROFILE:-}" ]; then
  if [ -z "${CODESIGN_IDENTITY:-}" ]; then
    echo "NOTARY_PROFILE requires CODESIGN_IDENTITY (Developer ID Application)." >&2
    exit 1
  fi
  xcrun notarytool submit "$dmg_path" --keychain-profile "$NOTARY_PROFILE" --wait
  xcrun stapler staple "$dmg_path"
  xcrun stapler validate "$dmg_path"
fi
echo "DONE: $dmg_path"
