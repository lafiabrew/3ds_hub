#!/bin/sh
# Build with the official pinned Pages stack; no host Ruby or credentials.
set -eu
[ "$#" -eq 1 ] || { printf 'Usage: sh tests/pages/build_pages.sh EMPTY_OUTPUT_DIR\n' >&2; exit 2; }
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
out=$(python3 - "$root" "$1" <<'PY'
from pathlib import Path
import sys
root, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
if out == root or root in out.parents:
    raise SystemExit('Output must be outside the source checkout')
if out.exists() and (not out.is_dir() or any(out.iterdir())):
    raise SystemExit('Use a new empty output directory; preserve previous build evidence')
out.mkdir(parents=True, exist_ok=True)
print(out)
PY
)
image=ghcr.io/actions/jekyll-build-pages@sha256:6791ebfd912185ed59bfb5fb102664fa872496b79f87ff8b9cfba292a7345041
log=$(mktemp "${TMPDIR:-/tmp}/3ds-pages-build.XXXXXX")
status=0
podman run --pull=never --rm --userns=keep-id --entrypoint /bin/bash \
  -v "$root:/workspace/src:ro,Z" -v "$out:/workspace/out:Z" \
  -e PAGES_REPO_NWO=lafiabrew/3ds_hub \
  -e JEKYLL_BUILD_REVISION=local-validation \
  -e PAGES_API_URL=https://api.github.com -e JEKYLL_ENV=production \
  "$image" -c 'cd /usr/local/bundle && exec ruby /workspace/src/tests/pages/build_pages.rb' >"$log" 2>&1 || status=$?
cat "$log"
if [ "$status" -ne 0 ]; then
  printf 'Build failed; evidence retained at %s\n' "$log" >&2
  exit "$status"
fi
if grep -Eq 'Liquid (Warning|Error|Exception)' "$log"; then
  printf 'Liquid diagnostic rejected; evidence retained at %s\n' "$log" >&2
  exit 1
fi
rm -f "$log"
