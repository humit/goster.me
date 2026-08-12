# AGENTS.md

This repository is developed with substantial AI assistance under experienced human technical direction.

AI agents are expected to behave as engineering collaborators, not autonomous product owners. The maintainer is an experienced senior Linux/platform engineer with production infrastructure, automation, CI/CD, release engineering, troubleshooting, reliability, virtualization, and incident ownership experience. Do not dilute technical communication into beginner-oriented explanations unless explicitly asked.

The purpose of this file is to define the engineering contract for AI-assisted work on goster.me.

## 1. Working model

- Human technical direction is authoritative for product intent, risk tolerance, production changes, and architecture.
- AI may inspect, reason, implement, test, document, review, and propose improvements.
- AI must not silently broaden scope, weaken security controls, change deployment semantics, or reinterpret product requirements.
- Prefer evidence from the current repository and running system over assumptions.
- Inspect before editing. Verify before claiming completion.
- Use small, reviewable changes. Avoid speculative rewrites of working code.
- When a change affects production behavior, make rollback and verification part of the change.

## 2. Product principles

The product goal is content minimization: show the content the user wants while removing unnecessary navigation, advertising, recommendations, engagement surfaces, and other distraction.

Core behavior:

- prefer clean provider embeds when available;
- isolate source-page applications only when a clean embed does not exist;
- fail closed for unknown or unsupported content;
- keep the public UI minimal, mobile-first, understandable, and low-dependency;
- do not add product chrome that competes with the content;
- preserve useful interactive behavior rather than cosmetically simplifying it until it breaks.

## 3. Security invariants

Security rules are architectural constraints, not adapter-specific conveniences.

- Third-party source HTML/JavaScript must never execute with the primary goster.me origin.
- Isolated third-party applications must use the dedicated sandbox origin and browser sandbox restrictions.
- Do not add `allow-same-origin` to isolated third-party content without an explicit security review.
- URL validation, redirect validation, SSRF protection, and network policy remain centralized.
- Adapters classify and discover content; they must not implement weaker parallel fetch/security paths.
- Unknown content fails closed rather than falling back to unrestricted remote HTML.
- Sandbox storage access remains read-only where designed.
- Signed sandbox access remains fail-closed.
- Keep secrets out of the repository, logs, test fixtures, documentation, and chat output.
- Public security documentation should explain guarantees and trust boundaries without unnecessarily publishing operational details. Security must not depend on obscurity, but unnecessary disclosure is not a goal.

Before changing security-sensitive code, read the security architecture documents in `docs/`.

## 4. Git and branch model

Target steady-state model:

- `main` is the canonical production deployment branch.
- Production must not intentionally run from `feature/*`, `security/*`, `experiment/*`, or `refactor/*` branches.
- Feature and refactor branches should normally start from the current `main`.
- Staging is an environment, not a long-lived integration branch.
- A candidate branch/commit is staged by exact Git SHA.
- After staging validation, the change is merged to `main`.
- Production deploys the exact resulting `main` commit.
- Record the deployed SHA and retain the previous known-good SHA for rollback.
- Rollback means deploying a previously known-good commit, not switching production to an arbitrary feature branch.

During the transition to this model, do not rewrite shared history or force-move `main` merely to make branch topology look clean. Resolve divergence explicitly and preserve meaningful history.

## 5. Staging and production discipline

A production deployment procedure must be reproducible and should eventually be exposed through a small repository-owned tool rather than a sequence of ad-hoc shell commands.

Desired interface:

```text
tools/goster stage <ref>
tools/goster stage-status
tools/goster stage-test
tools/goster deploy-main
tools/goster prod-status
tools/goster rollback
```

Expected semantics:

### Staging

- fetch remote state;
- resolve the requested ref to an exact SHA;
- use a disposable worktree or equivalent isolated checkout;
- use staging-only listeners/state;
- never collide with production listeners or production mutable state;
- run the full regression suite;
- run representative real-content smoke tests when relevant;
- report the exact staged SHA.

### Production

- deploy only from `main`;
- require a clean and understood checkout state;
- resolve and record the exact `origin/main` SHA;
- validate before switching traffic or restarting critical services;
- restart dependencies in a safe order;
- run HTTP/service/process smoke tests after deployment;
- record the successful deployed SHA;
- leave a clear rollback target.

Deployment scripts should abort on failed preconditions rather than attempting to repair an ambiguous production state automatically.

## 6. Production filesystem and privilege rules

- Repository/application operations in the production application tree are performed as the application service user unless root privileges are genuinely required.
- Privileged operations are reserved for service management, reverse proxy configuration, ownership/permissions, and other OS-level changes.
- Do not use destructive cleanup commands on the live checkout.
- Do not use `git clean` on production.
- Do not use `git reset --hard` on the live production checkout as a normal deployment mechanism.
- A destructive reset may be acceptable only in a clearly disposable staging worktree whose local state is explicitly known to be throwaway.
- Do not delete or recreate the production virtual environment casually.
- Never replace the reverse-proxy configuration wholesale when a targeted merge/edit preserves existing protections and logging.

## 7. Change strategy

Prefer this order:

1. inspect current implementation and call sites;
2. identify behavioral and security invariants;
3. make the smallest coherent change;
4. add or update tests that express the intended behavior;
5. run the relevant focused tests;
6. run the full regression suite before a deployment milestone;
7. stage the exact commit;
8. perform representative functional/browser checks;
9. merge to `main`;
10. deploy the exact `main` commit and verify it.

Do not claim a test or deployment passed unless its result was actually observed.

## 8. Refactoring rules

Refactors must be behavior-preserving unless behavior change is explicitly part of the task.

Current adapter refactor direction:

- reduce the monolithic adapter module;
- move toward explicit, modular site/provider adapters;
- keep registration understandable and deterministic;
- avoid an opaque dynamic plugin system unless there is a demonstrated need;
- remove temporary monkeypatch-style adapter extensions as they gain proper module ownership;
- keep security/network policy centralized;
- keep rendering policy separate from site classification;
- prefer declarative fingerprints where they improve clarity without hiding behavior.

A safe migration may use a new package name as a compatibility layer before replacing an existing module name. Do not create ambiguous Python import layouts casually.

## 9. Adapter development

- Start from real URLs and observed DOM/application behavior.
- Prefer explicit fingerprints over broad scraping heuristics.
- Prefer clean embeds over native-page isolation.
- Site-specific compatibility fixes should remain site-specific where a global change could regress other adapters.
- Preserve required application states, not only the first visible screen.
- Validate both normal interaction and completion/result states when practical.
- Treat external navigation escape, injected advertising/tracking execution, and broken scrolling/input as separate concerns; do not solve one by weakening another security boundary.

## 10. Testing expectations

At a minimum, changes should run the tests relevant to the touched area. Before production milestones, run the full suite.

Security-sensitive and platform changes should verify, as applicable:

- expected success paths;
- fail-closed paths;
- malformed/hostile input;
- redirect handling;
- short-link persistence/expiry;
- sandbox authorization and direct-access rejection;
- storage limits/maintenance;
- process/service health;
- public HTTP behavior;
- representative browser behavior for embeds and isolated applications.

Tests must use isolated temporary state rather than production mutable data.

## 11. Operational communication

When collaborating with the maintainer:

- use concise, technically precise language;
- assume familiarity with Linux, networking, systemd, Git, reverse proxies, Python, CI/CD, infrastructure, and production operations;
- explain non-obvious tradeoffs and failure modes rather than basic command syntax;
- provide copy/paste-ready commands when remote execution must be performed manually;
- keep commands staged so state can be inspected between risky transitions;
- clearly distinguish inspection, mutation, validation, and rollback steps;
- never ask for information that can be safely obtained from the repository or connected tooling;
- if uncertain about a production-affecting fact, inspect it rather than guessing.

For meaningful engineering increments, make the reasoning explicit at the appropriate level:

- **Why** — the problem, risk, or opportunity being addressed;
- **What** — the concrete scope and intended outcome;
- **How** — the implementation or operational mechanism;
- **Risk / blast radius** — what could regress and which invariants are involved;
- **Validation** — observable acceptance criteria;
- **Rollback** — the safe recovery path when relevant;
- **Next** — the smallest useful next increment.

Use low-level detail when it affects correctness and high-level architecture when it affects system direction. Do not add explanation merely for ceremony.

## 12. AI provenance

AI-assisted development is intentional and should be visible rather than disguised.

However, provenance does not reduce engineering standards. AI-generated changes are held to the same requirements as human-written changes: clear ownership, understandable architecture, tests, security review proportional to risk, reproducible deployment, and production verification.

The desired authorship model is:

```text
experienced human engineering direction
            +
AI-assisted implementation / analysis / review
            =
reviewable, testable, operable software
```

Do not add generated-code banners to every source file. This repository-level document is the canonical statement of the AI-assisted development model.

## 13. Documentation discipline

- Keep public documentation useful to contributors and operators without turning it into an unnecessary map of production internals.
- Document architectural invariants and operational contracts.
- Keep secrets, live credentials, private identifiers, and unnecessary infrastructure specifics out of public documentation.
- Update documentation when an architectural or deployment contract changes.
- Prefer one canonical statement over duplicated instructions that can drift.

## 14. Definition of done

A change is not done merely because code was produced.

Depending on scope, completion requires:

- implementation is understandable and scoped;
- tests pass;
- security invariants remain intact;
- deployment/runtime assumptions are explicit;
- staging validation is complete when required;
- production verification is complete when deployed;
- documentation is updated if the engineering contract changed;
- known residual issues are recorded rather than hidden.

## 15. Lightweight Scrum / SAFe-style tracking

Use GitHub Issues when tracking creates engineering value; do not create tickets merely to imitate process.

An issue is normally worthwhile when work has one or more of these properties:

- spans multiple coherent increments or commits;
- carries meaningful production/security/operational risk;
- needs explicit acceptance criteria or Definition of Done;
- contains architectural decisions or non-goals worth preserving;
- is likely to continue across sessions or contributors;
- has dependencies, follow-up work, or residual issues that could otherwise be lost;
- represents an epic/capability whose progress should remain visible independently of a single PR.

Small self-contained fixes may remain entirely within a PR when an issue would add no useful information.

For substantial work, prefer this lifecycle:

```text
Issue / Epic
    -> Why + Outcome + constraints
    -> small implementation increments
    -> feature/refactor branch from main
    -> exact-SHA staging and validation
    -> PR linked to the issue
    -> merge to main
    -> production verification where applicable
    -> close issue when its Definition of Done is actually satisfied
```

Issue content should be concise but operationally useful. Include as appropriate:

- Why / problem statement;
- intended Outcome;
- increments or acceptance criteria;
- Non-goals when scope control matters;
- Risk / blast radius and safety invariants;
- dependencies or blockers;
- Definition of Done;
- known residual/follow-up work.

Treat issue checklists as planning and evidence aids, not as substitutes for observed validation. Update issues when the plan materially changes, and close them only when the documented outcome is achieved or explicitly marked not planned.
