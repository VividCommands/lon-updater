#!/usr/bin/env bash
# Build the Lon updater into a single Windows executable using PyInstaller.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v pyinstaller &>/dev/null; then
  echo "PyInstaller is not installed. Run 'pip install pyinstaller' first."
  exit 1
fi

# Remove previous builds
rm -rf build dist __pycache__ updater.spec || true

# Build a one‑file executable. The --clean flag removes any temporary files.
# We leave the console enabled so that log output is visible when run manually.
pyinstaller \
  --onefile \
  --name updater \
  --clean \
  updater.py

echo "Build complete. See dist/updater.exe"