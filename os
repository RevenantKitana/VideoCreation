#!/bin/sh
# Mac/Linux wrapper: runs run.py inside this folder's own toolchain (.pixi).
cd "$(dirname "$0")"
export PIXI_HOME="$PWD/.tools/pixi-home"

# Automatically find any nvidia CUDA / cuDNN libraries in Python site-packages
NV_LIBS=""
for p in .pixi/envs/default/lib/python*/site-packages/nvidia/*/lib; do
  if [ -d "$p" ]; then
    NV_LIBS="$NV_LIBS:$PWD/$p"
  fi
done

export LD_LIBRARY_PATH="/usr/local/cuda/lib64:/usr/local/cuda-12/lib64:/usr/local/cuda/targets/x86_64-linux/lib:/usr/lib/x86_64-linux-gnu:/usr/local/nvidia/lib64:/usr/local/nvidia/lib$NV_LIBS:${LD_LIBRARY_PATH:-}"
exec ./.tools/pixi run --quiet python run.py "$@"
