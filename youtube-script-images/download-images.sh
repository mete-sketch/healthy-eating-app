#!/usr/bin/env bash
#
# Downloads all 220 generated images, naming each file by its script timestamp
# (e.g. the frame for 0:04 is saved as "0:04.png"). Run this on your own
# machine — the cloud session that generated the images cannot reach the CDN
# because of an outbound network policy.
#
# Usage:
#   ./download-images.sh                # names files "0:04.png" (literal colon)
#   ./download-images.sh --safe         # names files "0-04.png" (Windows/macOS-safe)
#
# Output: ./images/<timestamp>.png
#
# Note: a few timestamps repeat in the script (two lines share one on-screen
# time). Those get a "b" suffix so nothing is overwritten, e.g. "2:38.png" and
# "2:38b.png".

set -euo pipefail
cd "$(dirname "$0")"

SAFE=0
[[ "${1:-}" == "--safe" ]] && SAFE=1

mkdir -p images
ok=0; fail=0

while IFS=$'\t' read -r ts url; do
  [[ -z "$ts" ]] && continue
  name="$ts"
  if [[ $SAFE -eq 1 ]]; then
    name="${name//:/-}"
  fi
  if curl -fsSL -o "images/${name}.png" "$url"; then
    ok=$((ok+1))
  else
    echo "FAILED: $ts -> $url" >&2
    fail=$((fail+1))
  fi
done < filelist.tsv

echo "Downloaded ${ok} images into ./images  (failures: ${fail})"
