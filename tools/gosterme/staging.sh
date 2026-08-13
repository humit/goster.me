# Exact-SHA staging worktree management and regression execution.

resolve_ref() {
    local ref="$1"
    local candidate

    if run_app git -C "$APP_ROOT" show-ref --verify --quiet "refs/remotes/origin/${ref}"; then
        candidate="origin/${ref}"
    else
        candidate="$ref"
    fi

    run_app git -C "$APP_ROOT" rev-parse --verify "${candidate}^{commit}"
}

write_stage_state() {
    local ref="$1"
    local sha="$2"

    run_app mkdir -p "$STAGE_ROOT"
    printf 'ref=%s\nsha=%s\n' "$ref" "$sha" \
        | run_app tee "$STAGE_STATE" >/dev/null
    run_app chmod 0640 "$STAGE_STATE"
}

read_state_value() {
    local key="$1"
    [ -f "$STAGE_STATE" ] || return 1
    run_app awk -F= -v key="$key" \
        '$1 == key {print substr($0, length(key) + 2)}' "$STAGE_STATE"
}

cmd_stage() {
    local ref="${1:-}"
    [ -n "$ref" ] || die "usage: tools/goster stage <ref>"

    require_repo
    fetch_origin

    local sha
    sha="$(resolve_ref "$ref")"

    log "resolved $ref -> $sha"
    run_app mkdir -p "$STAGE_ROOT"

    if [ -e "$STAGE_DIR" ]; then
        log "removing previous disposable stage worktree"
        run_app git -C "$APP_ROOT" worktree remove --force "$STAGE_DIR"
    fi

    run_app git -C "$APP_ROOT" worktree prune
    run_app git -C "$APP_ROOT" worktree add --detach "$STAGE_DIR" "$sha"

    write_stage_state "$ref" "$sha"

    local staged_sha
    staged_sha="$(run_app git -C "$STAGE_DIR" rev-parse HEAD)"
    [ "$staged_sha" = "$sha" ] \
        || die "staged SHA mismatch: expected $sha got $staged_sha"

    log "staged exact SHA: $sha"
    log "worktree: $STAGE_DIR"
    log "next: tools/goster stage-test"
}

cmd_stage_status() {
    require_repo

    if [ ! -d "$STAGE_DIR" ]; then
        log "stage: absent"
        return 0
    fi

    local sha ref state_sha
    sha="$(run_app git -C "$STAGE_DIR" rev-parse HEAD)"
    ref="$(read_state_value ref || true)"
    state_sha="$(read_state_value sha || true)"

    printf 'stage_dir: %s\n' "$STAGE_DIR"
    printf 'stage_ref: %s\n' "${ref:-unknown}"
    printf 'stage_sha: %s\n' "$sha"
    printf 'state_sha: %s\n' "${state_sha:-missing}"
    printf 'stage_clean: '
    if [ -z "$(run_app git -C "$STAGE_DIR" status --porcelain)" ]; then
        printf 'yes\n'
    else
        printf 'no\n'
    fi
}

load_signing_key() {
    if [ -n "${GOSTER_SANDBOX_SIGNING_KEY:-}" ]; then
        printf '%s' "$GOSTER_SANDBOX_SIGNING_KEY"
        return 0
    fi

    [ -r "$ENV_FILE" ] || sudo test -r "$ENV_FILE" \
        || die "cannot read environment file: $ENV_FILE"

    if [ "$(id -un)" = "$APP_USER" ]; then
        awk -F= \
            '$1=="GOSTER_SANDBOX_SIGNING_KEY" {print substr($0, index($0,"=")+1); exit}' \
            "$ENV_FILE"
    else
        sudo awk -F= \
            '$1=="GOSTER_SANDBOX_SIGNING_KEY" {print substr($0, index($0,"=")+1); exit}' \
            "$ENV_FILE"
    fi
}

cmd_stage_test() {
    require_path "$PYTHON"
    [ -d "$STAGE_DIR" ] \
        || die "stage worktree does not exist; run: tools/goster stage <ref>"

    local expected_sha actual_sha key test_db
    expected_sha="$(read_state_value sha || true)"
    actual_sha="$(run_app git -C "$STAGE_DIR" rev-parse HEAD)"

    [ -n "$expected_sha" ] || die "stage state is missing expected SHA"
    [ "$expected_sha" = "$actual_sha" ] \
        || die "stage state mismatch: expected $expected_sha got $actual_sha"
    [ -z "$(run_app git -C "$STAGE_DIR" status --porcelain)" ] \
        || die "stage worktree is not clean"

    key="$(load_signing_key)"
    [ "${#key}" -ge 32 ] || die "sandbox signing key is missing or too short"

    test_db="/tmp/goster-stage-test-${actual_sha}.sqlite3"
    run_app rm -f "$test_db"

    log "running full regression suite at exact SHA $actual_sha"
    run_app env \
        GOSTER_SANDBOX_SIGNING_KEY="$key" \
        GOSTER_SANDBOX_ORIGIN="https://s.goster.me" \
        GOSTER_DATABASE="$test_db" \
        bash -c 'cd "$1" && exec "$2" -m unittest discover -v' \
        bash "$STAGE_DIR" "$PYTHON"

    run_app rm -f "$test_db"
    log "stage tests passed: $actual_sha"
}
