#!/usr/bin/env bash
# Back up the single-host profile: one compressed PostgreSQL dump plus a small manifest.
# In this profile PostgreSQL holds everything that must survive (accounts, drafts, packs, settings, audit log,
# uploaded files, cache); Redis is rebuilt on start. With the retrieval overlay the search index is NOT backed up:
# it is rebuilt by re-indexing, so it is not listed as protected.
#   ./backup.sh [output-folder]        default: ./backups
#   KEEP=14 ./backup.sh ...            after writing, delete all but the newest 14 dumps (and their manifests) in the folder
# Run from this folder with the same -f files and environment you start the stack with (COMPOSE_FILE may be set).
set -euo pipefail
cd "$(dirname "$0")"
out="${1:-./backups}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
# Check KEEP before doing any work.
case "${KEEP:-1}" in (*[!0-9]*|0) echo "KEEP must be a whole number of at least 1" >&2; exit 1;; esac
mkdir -p "$out"
umask 077
dump="$out/nortpole-$stamp.dump"
# -Fc: compressed custom format; --no-owner so a restore works with a different database role.
docker compose exec -T db pg_dump -U nortpole -d nortpole -Fc --no-owner > "$dump"
size=$(wc -c < "$dump")
[ "$size" -gt 1000 ] || { echo "backup looks empty ($size bytes); removed" >&2; rm -f "$dump"; exit 1; }
sum=$(sha256sum "$dump" | cut -d' ' -f1)
head_rev=$(docker compose exec -T db psql -U nortpole -d nortpole -Atc "select version_num from alembic_version" 2>/dev/null | tr -d '\r' | paste -sd, - || true)
audit_rows=$(docker compose exec -T db psql -U nortpole -d nortpole -Atc "select count(*) from nortpole_audit_event" 2>/dev/null | tr -d '\r' || echo unknown)
cat > "$dump.manifest" <<MANIFEST
created_utc=$stamp
file=$(basename "$dump")
bytes=$size
sha256=__SUM__
migration_revision=$head_rev
audit_rows=$audit_rows
product_version=${NORTPOLE_VERSION:-${NORTPOLE_VERSION:-dev}}
MANIFEST
sed -i "s/__SUM__/$sum/" "$dump.manifest"
echo "wrote $dump ($size bytes)"
echo "wrote $dump.manifest"
if [ -n "${KEEP:-}" ]; then
  # Newest first; everything after the first KEEP entries goes. Only files this script names are touched.
  ls -1t "$out"/nortpole-*.dump 2>/dev/null | tail -n +"$((KEEP + 1))" | while read -r old; do
    rm -f -- "$old" "$old.manifest" && echo "removed old backup $(basename "$old")"
  done
fi
echo "Copy both files off this machine; a backup that lives only on the machine it protects is not a backup."
