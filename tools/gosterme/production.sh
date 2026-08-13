# Read-only production Git, service, and HTTP readiness inspection.

cmd_prod_preflight() {
    require_repo
    fetch_origin

    local branch head remote_main tracked_changes
    branch="$(run_app git -C "$APP_ROOT" symbolic-ref --quiet --short HEAD || true)"
    head="$(run_app git -C "$APP_ROOT" rev-parse HEAD)"
    remote_main="$(run_app git -C "$APP_ROOT" rev-parse origin/main)"
    tracked_changes="$(run_app git -C "$APP_ROOT" status --porcelain --untracked-files=no)"

    printf 'branch: %s\n' "${branch:-detached}"
    printf 'head: %s\n' "$head"
    printf 'origin_main: %s\n' "$remote_main"

    [ "$branch" = "main" ] || die "production checkout is not on main"
    [ -z "$tracked_changes" ] || die "production checkout has tracked changes"
    [ "$head" = "$remote_main" ] \
        || die "production HEAD does not match origin/main"

    log "production Git preflight passed"
}

service_pid() {
    systemctl show -p MainPID --value "$1" 2>/dev/null || true
}

probe_http_status() {
    local status
    if status="$(
        curl \
            --silent \
            --show-error \
            --connect-timeout 2 \
            --max-time 5 \
            --output /dev/null \
            --write-out '%{http_code}' \
            "$1" 2>/dev/null
    )"; then
        printf '%s' "$status"
    else
        printf '%s' "${status:-000}"
    fi
}

wait_for_http_status() {
    local url="$1" expected="$2" attempts="${3:-10}"
    local attempt status

    for ((attempt = 1; attempt <= attempts; attempt++)); do
        status="$(probe_http_status "$url")"
        if [ "$status" = "$expected" ]; then
            printf '%s\n' "$status"
            return 0
        fi
        [ "$attempt" -eq "$attempts" ] || sleep 1
    done

    printf '%s\n' "$status"
    return 1
}

cmd_prod_status() {
    require_repo

    local branch head main_pid sandbox_pid
    branch="$(run_app git -C "$APP_ROOT" symbolic-ref --quiet --short HEAD || true)"
    head="$(run_app git -C "$APP_ROOT" rev-parse HEAD)"
    main_pid="$(service_pid "$MAIN_SERVICE")"
    sandbox_pid="$(service_pid "$SANDBOX_SERVICE")"

    printf 'branch: %s\n' "${branch:-detached}"
    printf 'head: %s\n' "$head"
    printf 'main_service: %s\n' "$(systemctl is-active "$MAIN_SERVICE" 2>/dev/null || true)"
    printf 'main_pid: %s\n' "${main_pid:-0}"
    printf 'sandbox_service: %s\n' "$(systemctl is-active "$SANDBOX_SERVICE" 2>/dev/null || true)"
    printf 'sandbox_pid: %s\n' "${sandbox_pid:-0}"

    if command -v curl >/dev/null 2>&1; then
        local http_failed=0
        printf 'home_http: '
        wait_for_http_status https://goster.me/ 200 || http_failed=1
        printf 'sandbox_bare_http: '
        wait_for_http_status https://s.goster.me/v/invalid 404 || http_failed=1
        [ "$http_failed" -eq 0 ] || die "production HTTP readiness checks failed"
    fi
}
