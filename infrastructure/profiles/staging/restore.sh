#!/usr/bin/env bash
# Restore a backup made by backup.sh into the running single-host profile. This REPLACES the current database.
#   ./restore.sh <backup.dump> [--yes]
# Steps: check the checksum against the manifest, stop the API, drop and recreate the database, load the dump,
# start the API (it applies any newer migrations), then check the audit log chain.
set -euo pipefail
cd "$(dirname "$0")"
dump="${1:?usage: restore.sh <backup.dump> [--yes]}"
[ -f "$dump" ] || { echo "no such file: $dump" >&2; exit 1; }
if [ -f "$dump.manifest" ]; then
  want=$(grep '^sha256=' "$dump.manifest" | cut -d= -f2)
  have=$(sha256sum "$dump" | cut -d' ' -f1)
  [ "$want" = "$have" ] || { echo "checksum does not match the manifest; refusing to restore" >&2; exit 1; }
  echo "checksum matches the manifest"
else
  echo "warning: no manifest next to the dump, so the checksum was not verified" >&2
fi
if [ "${2:-}" != "--yes" ]; then
  read -r -p "This replaces the current database. Type 'replace' to continue: " ans
  [ "$ans" = "replace" ] || { echo "cancelled"; exit 1; }
fi
docker compose stop api web >/dev/null
docker compose exec -T db psql -U nortpole -d postgres -v ON_ERROR_STOP=1 -c "drop database if exists nortpole with (force)" -c "create database nortpole owner nortpole" >/dev/null
docker compose exec -T db pg_restore -U nortpole -d nortpole --no-owner --exit-on-error < "$dump"
docker compose up -d api web >/dev/null
echo "restored; waiting for the API"
for i in $(seq 1 60); do
  docker compose ps api --format '{{.Health}}' | grep -q healthy && break
  sleep 3
done
docker compose ps api --format '{{.Name}} {{.Health}}'
echo "Next: sign in as an administrator and open Admin > Governance > Audit log, or call GET /admin/audit/verify; the chain should read intact."
