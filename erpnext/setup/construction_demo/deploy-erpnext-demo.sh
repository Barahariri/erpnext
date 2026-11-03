#!/usr/bin/env bash
# TEST ONLY. Replaces only six Frappe application containers.
# Does NOT drop databases, touch Laravel, run prune, or call down -v.
set -Eeuo pipefail

COMPOSE=/root/erpnext-compose.yml
OVERRIDE=/root/erpnext-construction.override.yml
BUILDDIR=/root/frappe-docker-construction-build
IMAGE=local/erpnext-construction-demo:16
SITE=erp.yourdomain.com

fail() { echo "ERROR: $*" >&2; exit 1; }
test -f "$COMPOSE" || fail "Missing $COMPOSE"
command -v docker >/dev/null || fail "Docker required"
command -v git >/dev/null || fail "Git required"
command -v python3 >/dev/null || fail "Python required"

project="$(docker inspect erpnext-backend-1 --format '{{index .Config.Labels "com.docker.compose.project"}}')"
test "$project" = erpnext || fail "Unexpected Docker project $project"

# Check all six images are the known ERPNext image. NEVER modify Laravel apps.
docker compose -p erpnext -f "$COMPOSE" config --format json |
python3 -c '
import json, sys
services = json.load(sys.stdin)["services"]
wanted = ("backend", "frontend", "queue-short", "queue-long", "scheduler", "websocket")
allowed = {"frappe/erpnext:v16.53.0", "local/erpnext-construction-demo:16"}
for name in wanted:
    if name not in services or services[name].get("image") not in allowed:
        raise SystemExit("Refusing unexpected service image: " + name)
print("ERPNext-only service images verified:", ", ".join(wanted))
' || fail "Compose images have changed; no deployment performed"

cat > "$OVERRIDE" <<'OVERRIDE_FILE'
services:
  backend:
    image: local/erpnext-construction-demo:16
    pull_policy: never
  frontend:
    image: local/erpnext-construction-demo:16
    pull_policy: never
  queue-short:
    image: local/erpnext-construction-demo:16
    pull_policy: never
  queue-long:
    image: local/erpnext-construction-demo:16
    pull_policy: never
  scheduler:
    image: local/erpnext-construction-demo:16
    pull_policy: never
  websocket:
    image: local/erpnext-construction-demo:16
    pull_policy: never
OVERRIDE_FILE
docker compose -p erpnext -f "$COMPOSE" -f "$OVERRIDE" config --quiet

if test -d "$BUILDDIR/.git"; then
  git -C "$BUILDDIR" pull --ff-only
else
  test ! -e "$BUILDDIR" || fail "Unexpected existing builder path"
  git clone --depth=1 https://github.com/frappe/frappe_docker.git "$BUILDDIR"
fi
cd "$BUILDDIR"
cat > apps.json <<'APPS'
[
  {"url":"https://github.com/Barahariri/erpnext",
   "branch":"feature/construction-enterprise-demo"},
  {"url":"https://github.com/frappe/hrms",
   "branch":"version-16"}
]
APPS

echo "Building image first; existing containers stay running until this succeeds."
build_cache_flags=()
if [[ "${DEMO_NO_CACHE:-0}" == "1" ]]; then
  build_cache_flags+=(--no-cache)
fi
DOCKER_BUILDKIT=1 docker build "${build_cache_flags[@]}" \
  --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
  --build-arg=FRAPPE_BRANCH=version-16 \
  --secret=id=apps_json,src=apps.json \
  --tag="$IMAGE" \
  --file=images/layered/Containerfile .

docker run --rm --entrypoint bash "$IMAGE" -lc \
  'bench version && test -f apps/erpnext/erpnext/setup/construction_demo/seed.py && test -d apps/hrms/hrms' \
  || fail "Built image does not contain the seeder and HRMS"

echo "Recreating ERPNext application containers only. DB/Redis/Laravel untouched."
docker compose -p erpnext -f "$COMPOSE" -f "$OVERRIDE" \
  up -d --no-deps --no-build \
  backend frontend queue-short queue-long scheduler websocket

docker exec erpnext-backend-1 bench version
docker exec erpnext-backend-1 bench --site "$SITE" list-apps
echo "DONE: code switched. Site DB was not reset or seeded."
echo "For future Compose operations, include both:"
echo "  -f $COMPOSE -f $OVERRIDE"
