# Deployment workflow

This document defines the target deployment contract for goster.me. It complements `AGENTS.md` with operator-facing detail.

## Why

Production changes have historically been applied through manually coordinated Git, systemd, Caddy, and verification steps. The goal is to retain the safe-change discipline while making the process reproducible, observable, and exact-SHA based.

## Branch and environment model

- `main` is the canonical production branch.
- Feature/refactor branches are never the intended production source.
- Staging is an environment, not a long-lived branch.
- A staging candidate is resolved to an exact Git SHA.
- The exact staged SHA is recorded and validated before promotion.
- Production deploys the exact resulting `main` SHA.
- Rollback targets a previously recorded known-good production SHA.

## Environment layout

Production checkout:

```text
/opt/goster.me
```

Disposable staging checkout:

```text
/opt/goster.me/.stage/current
```

Staging state:

```text
/opt/goster.me/.stage/state
```

The stage worktree is disposable. Production mutable data is not.

## Current increment

The first workflow increment is deliberately read-mostly for production. It proves the state model before adding deployment mutation commands.

```text
tools/goster stage <ref>
tools/goster stage-status
tools/goster stage-test
tools/goster prod-preflight
tools/goster prod-status
```

### `stage <ref>`

- fetches/prunes `origin`;
- resolves a remote branch or explicit commit-ish to an exact SHA;
- replaces only the known disposable stage worktree;
- checks out that SHA detached;
- records requested ref and exact SHA;
- verifies the resulting worktree HEAD matches the recorded SHA.

### `stage-status`

Reports the stage ref, exact worktree SHA, recorded state SHA, and whether the stage worktree is clean.

### `stage-test`

- refuses to run if stage state and worktree SHA differ;
- refuses to run on a dirty stage worktree;
- uses isolated temporary SQLite state;
- runs the full unittest discovery from the stage worktree directory so imports come from the staged code rather than the production checkout;
- never prints the sandbox signing secret.

The current production Python environment is reused for this first increment. Dependency-environment isolation is a separate concern and should be introduced when dependency changes require it.

### `prod-preflight`

Fetches `origin` and verifies:

- production checkout branch is `main`;
- tracked production files are clean;
- production HEAD exactly equals `origin/main`.

It does not change the production checkout.

### `prod-status`

Reports production branch/SHA, platform/sandbox service activity and PIDs, plus basic public HTTP observations.

## Safety boundaries

- Never use `git clean` on production.
- Do not use `git reset --hard` as the normal production deployment mechanism.
- Only the known `.stage/current` worktree may be force-removed as disposable stage state.
- Production and staging must not share mutable application state when staging services are introduced.
- Production mutation commands must abort on ambiguous state rather than attempting silent repair.
- Existing systemd hardening and Caddy protections are preserved.

## Next increment

After validating this state model on the production host:

1. add staging platform/sandbox listeners on dedicated non-production ports;
2. add representative HTTP smoke tests against those listeners;
3. record staged validation evidence;
4. implement `deploy-main` with exact-main-SHA checks and ordered service restart;
5. record `current` and `previous` production SHAs;
6. implement and test `rollback` against a known-good SHA.

`deploy-main` and `rollback` must not be added merely for API completeness. They should be introduced only after the precondition/state model has been exercised successfully on the real host.
