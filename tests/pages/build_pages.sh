#!/bin/sh
# Real immutable Pages stack, RO source, owned NEW output; no host Ruby needed.
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
runtime=${CONTAINER_RUNTIME:-podman}
case "$runtime" in
  podman) set -- --userns=keep-id ;;
  docker) set -- --user "$(id -u):$(id -g)" ;;
  *) printf 'CONTAINER_RUNTIME must be podman or docker\n' >&2; exit 2 ;;
esac
command -v "$runtime" >/dev/null
command -v timeout >/dev/null
owner=$(mktemp -d "${TMPDIR:-/tmp}/3ds-pages-build.XXXXXX")
label=$(basename "$owner")
log=$owner/build.log
cleanup() {
  status=$?
  trap - EXIT INT TERM
  if ids=$(timeout 15 "$runtime" ps -aq --no-trunc --filter "label=3ds.docs-owner=$label"); then
    if [ -n "$ids" ]; then
      # IDs come only from the owned unique label; never kill by a broad name.
      for cid in $ids; do
        if ! timeout 30 "$runtime" rm -f "$cid" >/dev/null 2>&1; then status=1; fi
      done
      if left=$(timeout 15 "$runtime" ps -aq --no-trunc --filter "label=3ds.docs-owner=$label"); then
        [ -z "$left" ] || status=1
      else status=1; fi
    fi
  else status=1; fi
  if [ "$status" -eq 0 ]; then rm -rf "$owner";
  else printf 'Build/cleanup failed; ownership/log receipt retained at %s (label %s)\n' "$owner" "$label" >&2; fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
printf 'Owned docs builder label %s; receipt %s\n' "$label" "$owner" >&2
image=ghcr.io/actions/jekyll-build-pages@sha256:6791ebfd912185ed59bfb5fb102664fa872496b79f87ff8b9cfba292a7345041
status=0
"$runtime" run --pull=never --rm "$@" --entrypoint /bin/bash \
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,exec,nosuid,size=512m -e HOME=/tmp \
  --label "3ds.docs-owner=$label" --cidfile "$owner/container.cid" \
  -v "$root:/workspace/src:ro,Z" -v "$out:/workspace/out:Z" \
  -e PAGES_REPO_NWO=lafiabrew/3ds_hub -e JEKYLL_GITHUB_TOKEN \
  -e "JEKYLL_BUILD_REVISION=${GITHUB_SHA:-local-validation}" \
  -e PAGES_API_URL=https://api.github.com -e JEKYLL_ENV=production \
  "$image" -c 'cd /usr/local/bundle && exec ruby /workspace/src/tests/pages/build_pages.rb' >"$log" 2>&1 || status=$?
cat "$log"
[ "$status" -eq 0 ] || exit "$status"
if grep -Eq 'Liquid (Warning|Error|Exception)' "$log"; then
  printf 'Liquid diagnostic rejected\n' >&2
  exit 1
fi
