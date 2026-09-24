#!/bin/bash
# One-time setup on a Mac. Double-click it, or let the AI agent run it:
#     bash setup/setup-mac.command
# Installs everything INTO this folder (.tools/, .pixi/, models/, engine/remotion/node_modules).
# Needs internet once (~2.5 GB of downloads). No admin password, no Homebrew, no API keys.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
export PIXI_HOME="$ROOT/.tools/pixi-home"

echo "== 1/5 pixi (the folder's own package manager)"
mkdir -p .tools
if [ ! -x .tools/pixi ]; then
  case "$(uname -m)" in
    arm64) ARCH=aarch64-apple-darwin ;;
    *)     ARCH=x86_64-apple-darwin ;;
  esac
  curl -fsSL "https://github.com/prefix-dev/pixi/releases/latest/download/pixi-$ARCH.tar.gz" | tar -xz -C .tools
  chmod +x .tools/pixi
fi

echo "== 2/5 Python, Manim, ffmpeg, Node, VieNeu (from the lockfile)"
./.tools/pixi install

echo "== 3/5 Remotion"
( cd engine/remotion && "$ROOT/.tools/pixi" run --manifest-path "$ROOT/pixi.toml" npm ci --no-audit --no-fund )
( cd engine/remotion && "$ROOT/.tools/pixi" run --manifest-path "$ROOT/pixi.toml" npx remotion browser ensure )

echo "== 4/5 Voice models (downloaded once into models/)"
./.tools/pixi run python run.py warmup

echo "== 5/5 Check"
chmod +x os
./os doctor
