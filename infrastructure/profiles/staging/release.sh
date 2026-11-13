#!/usr/bin/env bash
# Write a release manifest for the images that are tagged with a version.
#   ./release.sh manifest <version> [output-file]       default output: ./release-<version>.json
# Records the product commit, the image IDs for both images, the migration head found in the core source and the
# time. It reads what is built on this machine; it does not build, push or sign anything.
set -euo pipefail
cd "$(dirname "$0")"
cmd="${1:-}"; ver="${2:-}"
[ "$cmd" = "manifest" ] && [ -n "$ver" ] || { echo "usage: release.sh manifest <version> [output-file]" >&2; exit 2; }
out="${3:-./release-$ver.json}"
repo=../../..
core_id=$(docker image inspect "evolvxsi-core:$ver" --format '{{.Id}}')
web_id=$(docker image inspect "evolvxsi-web:$ver" --format '{{.Id}}')
commit=$(git -C "$repo" rev-parse HEAD)
dirty=$(git -C "$repo" status --porcelain | wc -l | tr -d ' ')
# The newest migration is the one no other migration names as its parent.
migrations="$repo/services/core/alembic/versions"
[ -d "$migrations" ] || { echo "migrations folder not found: $migrations" >&2; exit 1; }
head_rev=$(python3 - "$migrations" <<'PY'
import re, sys, pathlib
revs, parents = set(), set()
for f in pathlib.Path(sys.argv[1]).glob("*.py"):
    t = f.read_text()
    r = re.search(r'^revision(?::\s*str)?\s*=\s*["\']([0-9a-z]+)["\']', t, re.M)
    d = re.search(r'^down_revision(?::[^=]+)?\s*=\s*(.+)$', t, re.M)
    if r: revs.add(r.group(1))
    if d: parents.update(re.findall(r'["\']([0-9a-z]+)["\']', d.group(1)))
print(",".join(sorted(revs - parents)))
PY
)
cat > "$out" <<JSON
{
  "version": "$ver",
  "created_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "product_commit": "$commit",
  "uncommitted_files_at_build": $dirty,
  "images": {"core": "$core_id", "web": "$web_id"},
  "migration_head": "$head_rev"
}
JSON
echo "wrote $out"; cat "$out"
