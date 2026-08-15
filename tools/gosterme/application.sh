# Operator-facing application data and reporting commands.

cmd_feedback() {
    require_repo
    require_path "$PYTHON"
    if [ "${1:-}" = "notify" ]; then
        shift
        run_app env \
            GOSTER_TELEGRAM_BOT_TOKEN="$(read_env_value GOSTER_TELEGRAM_BOT_TOKEN)" \
            GOSTER_TELEGRAM_CHAT_ID="$(read_env_value GOSTER_TELEGRAM_CHAT_ID)" \
            "$PYTHON" "$APP_ROOT/feedback_telegram.py" "$@"
        return
    fi
    run_app "$PYTHON" "$APP_ROOT/feedback.py" "$@"
}

cmd_unsupported() {
    require_repo
    require_path "$PYTHON"
    run_app "$PYTHON" "$APP_ROOT/unsupported.py" "$@"
}

cmd_analytics() {
    require_repo
    require_path "$PYTHON"

    local key ssh_client="" arg
    local checkout_root
    local -a forwarded=()
    checkout_root="$(CDPATH= cd -- "${TOOL_DIR}/.." && pwd)"

    for arg in "$@"; do
        if [ "$arg" = "--exclude-current-ssh-client" ]; then
            [ -n "${SSH_CONNECTION:-}" ] \
                || die "SSH_CONNECTION is unavailable; use --exclude-ip <address>"
            ssh_client="${SSH_CONNECTION%% *}"
        else
            forwarded+=("$arg")
        fi
    done

    if [ -n "${GOSTER_ANALYTICS_KEY:-}" ]; then
        key="$GOSTER_ANALYTICS_KEY"
    elif [ -r "$ENV_FILE" ] || sudo test -r "$ENV_FILE"; then
        if [ "$(id -un)" = "$APP_USER" ]; then
            key="$(awk -F= \
                '$1=="GOSTER_ANALYTICS_KEY" {print substr($0, index($0,"=")+1); exit}' \
                "$ENV_FILE")"
        else
            key="$(sudo awk -F= \
                '$1=="GOSTER_ANALYTICS_KEY" {print substr($0, index($0,"=")+1); exit}' \
                "$ENV_FILE")"
        fi
    else
        key=""
    fi

    if [ -n "$ssh_client" ]; then
        forwarded+=("--exclude-ip" "$ssh_client")
    fi
    run_app env GOSTER_ANALYTICS_KEY="$key" \
        "$PYTHON" "$checkout_root/analytics_report.py" "${forwarded[@]}"
}
