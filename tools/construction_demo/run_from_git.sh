#!/usr/bin/env bash
# Isolated construction training data; NEVER run against the original erpnext project.
set -Eeuo pipefail

SRC=$(cd "$(dirname "$0")" && pwd)
BACKEND=erpnext-clean-backend-1
DB=erpnext-clean-db-1
SITE=frontend
DOMAIN=https://newerp.holotechnology.net
STATE=/root/erpnext-clean
mkdir -p "$STATE/runlogs"
umask 077

exec 9>"$STATE/.complete-seeder.lock"
flock -n 9 || { echo "STOP: Another seeder run is active"; exit 1; }

for filename in erpnext_clean_multicompany_v2.py erpnext_complete_v3.py verify_kit_static.py; do
  test -s "$SRC/$filename" || { echo "STOP: missing $filename"; exit 1; }
done
python3 "$SRC/verify_kit_static.py"

docker ps --format '{{.Names}}' | grep -qx "$BACKEND" || { echo "STOP: clean backend offline"; exit 1; }
docker ps --format '{{.Names}}' | grep -qx "$DB" || { echo "STOP: clean database offline"; exit 1; }
test "$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' "$BACKEND")" = erpnext-clean || { echo 'STOP: backend belongs to unexpected stack'; exit 1; }
test "$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' "$DB")" = erpnext-clean || { echo 'STOP: database belongs to unexpected stack'; exit 1; }

ACTUAL=$(docker exec -w /home/frappe/frappe-bench/sites "$BACKEND" \
  /home/frappe/frappe-bench/env/bin/python -c \
  'import json; print(json.load(open("frontend/site_config.json")).get("host_name", ""))')
test "$ACTUAL" = "$DOMAIN" || { echo "STOP: expected NEW site host $DOMAIN; found $ACTUAL"; exit 1; }
docker exec -w /home/frappe/frappe-bench "$BACKEND" test -f "sites/$SITE/site_config.json" || exit 1
docker exec -w /home/frappe/frappe-bench "$BACKEND" test -d apps/hrms || {
  echo "STOP: hrms source not present in local image, do not rebuild or install automatically"; exit 1; }

echo "Checked NEW stack: $BACKEND, site=$SITE, domain=$ACTUAL"
echo "Original erpnext frontend on port 8088 is NOT modified by this script."
for filename in erpnext_clean_multicompany_v2.py erpnext_complete_v3.py; do
  docker cp "$SRC/$filename" "$BACKEND:/tmp/$filename"
done

if [ "$#" -gt 0 ] && [ "$1" = "--audit" ]; then
  docker exec -w /home/frappe/frappe-bench/sites "$BACKEND" \
    /home/frappe/frappe-bench/env/bin/python /tmp/erpnext_complete_v3.py --phase audit
  exit
fi

LOG="$STATE/runlogs/complete_v3_$(date -u +%Y%m%dT%H%M%SZ).log"
exec > >(tee "$LOG") 2>&1
echo "Log: $LOG"
echo "=== Backing up isolated NEW site ==="
docker exec -w /home/frappe/frappe-bench "$BACKEND" bench --site "$SITE" backup

echo "=== HRMS app check (NEW site only) ==="
if ! docker exec -w /home/frappe/frappe-bench "$BACKEND" bench --site "$SITE" list-apps | awk '{print $1}' | grep -qx hrms; then
  docker exec -w /home/frappe/frappe-bench "$BACKEND" bench --site "$SITE" install-app hrms
fi

echo "=== Phase 1: companies, numbered accounts, projects, HR, inventory, fleet ==="
docker exec -w /home/frappe/frappe-bench/sites "$BACKEND" \
  /home/frappe/frappe-bench/env/bin/python /tmp/erpnext_clean_multicompany_v2.py --phase all

echo "=== Phase 2: September/October/November, banking, dashboards, audit ==="
docker exec -w /home/frappe/frappe-bench/sites "$BACKEND" \
  /home/frappe/frappe-bench/env/bin/python /tmp/erpnext_complete_v3.py --phase all

docker exec -w /home/frappe/frappe-bench "$BACKEND" bench --site "$SITE" clear-cache
echo '=== SUCCESS - verify that V3 printed CONSTRUCTION_DEMO_V3_READY ==='
