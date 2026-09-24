#!/bin/bash
# Build the zip you hand to staff:   bash tools/make_share_zip.sh [output-dir]
#
# Ships the instructions, engine, fonts, the aligner model (not downloadable anywhere —
# it must travel in the zip) and the two example videos. Leaves out everything setup
# rebuilds per laptop (.pixi, .tools, models/hf, node_modules) and all working files.
# Unzips to a folder named "xuong-tiktok", the name the guide (HUONG-DAN-SU-DUNG.pdf) uses.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
OUT="${1:-$HOME/Desktop}"
STAMP="$(date +%Y%m%d)"
STAGE="$(mktemp -d)/xuong-tiktok"

rsync -a \
  --exclude '.pixi/' --exclude '.tools/' --exclude '.cache/' --exclude 'models/hf/' \
  --exclude 'engine/remotion/node_modules/' --exclude '.DS_Store' --exclude '__pycache__/' \
  --exclude 'videos/*/build/' --exclude 'videos/*/voice/' --exclude 'videos/*/post.json' \
  --exclude 'videos/*/metrics/' --exclude 'days/*' --exclude 'voices/*' \
  --exclude 'goals/G-*' --exclude 'plans/*' --exclude 'findings/[0-9]*' \
  --exclude 'media/' --exclude 'dist/' --exclude 'models/kokoro/' --exclude 'models/espeak-ng-data/' \
  "$ROOT/" "$STAGE/"

[ -f "$STAGE/models/aligner/vi_ctc.onnx" ] || { echo "aligner model missing — refusing to build a broken zip"; exit 1; }
cp "$ROOT/docs/huong-dan/HUONG-DAN-SU-DUNG.pdf" "$STAGE/HUONG-DAN-SU-DUNG.pdf"
printf '# Findings\n\n| # | title | status |\n|---|---|---|\n' > "$STAGE/findings/INDEX.md"
chmod +x "$STAGE/os" "$STAGE/setup/setup-mac.command"

ZIP="$OUT/xuong-tiktok-aiducation-$STAMP.zip"
rm -f "$ZIP"
( cd "$(dirname "$STAGE")" && zip -r -X -q "$ZIP" xuong-tiktok )
rm -rf "$(dirname "$STAGE")"
echo "$ZIP ($(du -h "$ZIP" | cut -f1))"
