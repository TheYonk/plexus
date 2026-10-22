#!/usr/bin/env bash
# Clone the projects in deps.lock into DEPS/<name> at their pinned commits.
# An existing checkout is left as it is, with a note if it is not at the pin.
# Usage: scripts/deps.sh [DEPS dir, default: the directory above this repo]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPS="${1:-$(dirname "$HERE")}"
mkdir -p "$DEPS"
grep -vE '^\s*(#|$)' "$HERE/deps.lock" | while read -r name url commit; do
  dir="$DEPS/$name"
  if [[ -d "$dir/.git" ]]; then
    at="$(git -C "$dir" rev-parse HEAD)"
    if [[ "$at" == "$commit" ]]; then echo "$name: at $commit"; else echo "$name: exists at ${at:0:12}, pin is ${commit:0:12} (left alone; git -C $dir checkout $commit to match)"; fi
    continue
  fi
  echo "$name: cloning $url"
  git clone -q "$url" "$dir"
  git -C "$dir" -c advice.detachedHead=false checkout -q "$commit"
  echo "$name: at $commit"
done
