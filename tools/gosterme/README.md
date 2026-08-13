# gosterme operator CLI modules

`tools/goster` is the stable, legacy operator entrypoint. Keep it limited to
loading modules, displaying usage, and dispatching commands.

Command implementation belongs to the module that owns its operational domain:

- `common.sh`: shared configuration, privilege, repository, and environment helpers;
- `staging.sh`: exact-SHA staging worktrees and staged regression execution;
- `production.sh`: production Git preflight, service state, and HTTP readiness;
- `application.sh`: analytics, feedback, and unsupported-target commands.

When adding a command, place its implementation in the narrowest existing module,
add only its dispatch and usage text to `tools/goster`, and keep its tests in the
matching `test_tool_goster_*.py` module. Create another shell module only when a new
operational domain has distinct dependencies or lifecycle concerns.

The existing `tools/goster` path and `GOSTER_*` environment variables are
compatibility interfaces. Renaming them is outside this module split and requires
the migration process tracked separately by the repository naming work.
