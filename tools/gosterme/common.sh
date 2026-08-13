# Shared configuration, privilege handling, and repository helpers.

APP_ROOT="${GOSTER_APP_ROOT:-/opt/goster.me}"
APP_USER="${GOSTER_APP_USER:-gosterme}"
STAGE_ROOT="${GOSTER_STAGE_ROOT:-${APP_ROOT}/.stage}"
STAGE_DIR="${STAGE_ROOT}/current"
STAGE_STATE="${STAGE_ROOT}/state"
PYTHON="${GOSTER_PYTHON:-${APP_ROOT}/.venv/bin/python}"
ENV_FILE="${GOSTER_ENV_FILE:-/etc/goster.me/gosterme.env}"
MAIN_SERVICE="${GOSTER_MAIN_SERVICE:-gosterme.service}"
SANDBOX_SERVICE="${GOSTER_SANDBOX_SERVICE:-gosterme-sandbox.service}"

log() {
    printf '[goster] %s\n' "$*"
}

die() {
    printf '[goster] ERROR: %s\n' "$*" >&2
    exit 1
}

run_app() {
    if [ "$(id -un)" = "$APP_USER" ]; then
        "$@"
    else
        sudo -u "$APP_USER" -H "$@"
    fi
}

require_path() {
    [ -e "$1" ] || die "required path not found: $1"
}

require_repo() {
    require_path "${APP_ROOT}/.git"
    run_app git -C "$APP_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
        || die "not a Git work tree: $APP_ROOT"
}

fetch_origin() {
    log "fetching origin"
    run_app git -C "$APP_ROOT" fetch --prune origin
}

read_env_value() {
    local name="$1"
    if [ "$(id -un)" = "$APP_USER" ]; then
        awk -F= -v name="$name" \
            '$1==name {print substr($0, index($0,"=")+1); exit}' "$ENV_FILE"
    else
        sudo awk -F= -v name="$name" \
            '$1==name {print substr($0, index($0,"=")+1); exit}' "$ENV_FILE"
    fi
}
