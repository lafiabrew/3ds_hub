#!/bin/sh
# One fail-fast local journey; every attempt gets fresh, retained per-step logs.
set -eu
[ -n "${CHROMIUM_EXECUTABLE:-}" ] && [ -x "$CHROMIUM_EXECUTABLE" ] || {
  printf 'Set CHROMIUM_EXECUTABLE to a compatible installed browser\n' >&2; exit 2;
}
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$root"
work=$(mktemp -d "${TMPDIR:-/tmp}/3ds-composed-check.XXXXXX")
printf 'Validation workspace and logs: %s\n' "$work"
mkdir "$work/home"
run() {
  label=$1; shift
  status=0
  "$@" >"$work/$label.log" 2>&1 || status=$?
  cat "$work/$label.log"
  [ "$status" -eq 0 ] || exit "$status"
}
export PYTHONDONTWRITEBYTECODE=1
run privacy python3 tests/pages/check_privacy.py
run units python3 -m unittest discover -s tests -p test_pages_integration.py -v
run image podman pull ghcr.io/actions/jekyll-build-pages@sha256:6791ebfd912185ed59bfb5fb102664fa872496b79f87ff8b9cfba292a7345041
run docs sh tests/pages/build_pages.sh "$work/docs"
run catalogue python3 tests/pages/build_fixture_catalog.py --output "$work/catalog"
run compose python3 tools/compose_pages.py --catalog "$work/catalog" --docs "$work/docs" --output "$work/publication"
run sdk env HOME="$work/home" NPM_CONFIG_USERCONFIG=/dev/null npm install --prefix "$work/tools" --no-save --ignore-scripts --no-audit --no-fund playwright-core@1.58.2
export PLAYWRIGHT_MODULE_PATH="$work/tools/node_modules/playwright-core"
run browser node tests/pages/test_pages.cjs --site-dir "$work/publication"
run cleanup node tests/pages/test_pages.cjs --site-dir "$work/publication" --cleanup-probe
printf 'PASS: composed candidate; retained logs %s (not deployment acceptance)\n' "$work"
