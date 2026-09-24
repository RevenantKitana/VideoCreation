#!/bin/sh
# Mac wrapper: runs run.py inside this folder's own toolchain (.pixi), nothing global.
cd "$(dirname "$0")" && PIXI_HOME="$PWD/.tools/pixi-home" exec ./.tools/pixi run --quiet python run.py "$@"
