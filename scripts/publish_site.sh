#!/usr/bin/env bash
# Publish site/_build to the gh-pages branch of origin as one fresh commit.
# The branch is generated output (videos included), so it is replaced each
# time instead of growing a history of old videos. Run `make site` first.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="$HERE/site/_build"
REMOTE="$(git -C "$HERE" remote get-url origin)"
[[ -f "$BUILD/index.html" ]] || { echo "no $BUILD/index.html: run make site first"; exit 1; }
cd "$BUILD"
git init -q -b gh-pages
git add -A
git -c user.name="$(git -C "$HERE" config user.name)" -c user.email="$(git -C "$HERE" config user.email)" \
  commit -qm "Site build from $(git -C "$HERE" rev-parse --short HEAD)"
git push -qf "$REMOTE" gh-pages
rm -rf .git
echo "pushed site/_build to gh-pages on $REMOTE"
