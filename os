#!/bin/sh
# Mac/Linux wrapper: runs run.py inside this folder's own toolchain (.pixi).
cd "$(dirname "$0")"
export PIXI_HOME="$PWD/.tools/pixi-home"
export LD_LIBRARY_PATH="/usr/local/cuda/lib64:/usr/local/cuda-12/lib64:/usr/local/cuda/targets/x86_64-linux/lib:/usr/lib/x86_64-linux-gnu:/usr/local/nvidia/lib64:/usr/local/nvidia/lib:${LD_LIBRARY_PATH:-}"
exec ./.tools/pixi run --quiet python run.py "$@"
