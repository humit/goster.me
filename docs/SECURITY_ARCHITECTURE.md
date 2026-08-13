# goster.me Security Architecture

This document describes the security model of the public `goster.me` service at a level intended for maintainers and external reviewers. Operational secrets, exact deployment values, internal routes, timing parameters and host-specific details are intentionally omitted.

## Security goals

`goster.me` accepts user-supplied URLs and may retrieve content from third-party sites. The design therefore assumes that submitted URLs and remote content are untrusted.

The core goals are:

- prevent server-side request abuse;
- never execute third-party HTML or JavaScript with the authority of the primary `goster.me` origin;
- prefer provider-supported clean embeds whenever possible;
- isolate native third-party applications behind a separate security origin when no clean embed exists;
- fail closed for unknown or unsupported content;
- limit storage and process resource consumption;
- minimize tracking, advertising and unnecessary information disclosure.

## High-level trust model

```text
user URL
   |
   v
central URL / redirect validation
   |
   v
content classification
   |
   +---- clean provider embed ----> primary product shell
   |
   +---- native page content -----> isolated origin + browser sandbox
```

The isolated origin is a security boundary, not a cosmetic subdomain. Its hostname is deliberately not treated as a secret and does not provide authorization by itself.

## URL and network controls

All remote fetching must pass through centralized validation. Site adapters must not introduce weaker parallel fetch paths. Submitted URLs must use a multi-label DNS hostname; IP literals, legacy numeric IPv4 forms, single-label names, and invalid DNS labels are rejected before adapter resolution and are not added to the unsupported-target backlog.

The implementation applies scheme, host, redirect and destination validation and uses explicit source allowlists. Unsupported content does not fall back to arbitrary remote HTML execution.

## Rendering policy

There are two preferred rendering paths:

1. **Clean embed** — use a provider-supported embed when available.
2. **Isolated native content** — when an activity exists only inside a source page, classify it as isolated content and render it through the dedicated isolation service.

Adapters classify content and identify the relevant activity. They do not grant browser privileges.

## Isolation boundary

Third-party source HTML is never served as same-origin content from the primary application.

The isolation service is deliberately narrow:

- it serves only previously classified isolated content;
- it has read-only access to the short-link store;
- it cannot create or modify application data;
- it reuses the central URL and redirect validation path;
- it removes known advertising and analytics execution where practical;
- it is framed only by the primary product origin;
- it does not expose a general resolver or arbitrary file-serving interface.

Access to isolated content requires a short-lived signed capability produced by the primary service. The capability is intentionally time-bounded and is not a substitute for end-user authentication.

## Browser sandboxing

Isolated documents run inside browser sandbox restrictions in addition to being placed on a separate origin.

A critical invariant is that isolated third-party content must not regain same-origin authority with the primary application. Changes that weaken this boundary require a dedicated security review.

Content Security Policy and related browser controls further restrict framing, forms, plugins and other capabilities.

## Privacy and information minimization

The system removes known advertising and analytics execution from isolated content where practical. Public responses also avoid unnecessary backend implementation and version disclosure.

These are defense-in-depth and privacy measures. They do not replace origin separation or browser sandboxing.

The public feedback form stores only an allowlisted category, message text, receipt,
timestamps and review state. It does not request or persist a name, reply address,
IP address, User-Agent or referrer. Feedback is private to the operator, bounded by
row and database limits, protected by request and abuse controls, and automatically
removed after the configured retention window. The form uses short-lived signed
tokens as a browser-compatible fallback to origin metadata; the tokens require no
cookie and contain no visitor identifier.

Valid but unsupported targets are stored separately as a bounded adapter backlog.
Query strings and fragments are discarded, likely identifier-like path segments are
redacted, repeated host/path targets are counted in one row, and records expire. No
visitor tag is attached to this backlog. Optional Telegram feedback delivery sends
the submitted message to one operator-controlled chat using credentials held only in
the service environment; successful delivery state is persisted to prevent routine
duplicates.

## Storage and process controls

Application storage is bounded using row, payload and database-growth controls, with periodic maintenance of expired data.

Application processes run as a non-root service identity with restrictive systemd hardening and explicit CPU, memory, task and file-descriptor limits. Public traffic terminates at the reverse proxy; application listeners are not intended to be directly Internet-accessible.

## Adapter refactor invariants

Future adapter modularization must preserve the following rules:

1. adapters classify and discover content but do not bypass centralized network validation;
2. clean embeds are preferred to source-page isolation;
3. unknown content fails closed;
4. isolated content is rendered only through the dedicated isolation origin;
5. third-party HTML/JavaScript is never served with the primary origin's authority;
6. isolated browser content must not receive same-origin privileges with the primary application;
7. the isolation service remains read-only with respect to application storage;
8. direct knowledge of an isolated content identifier is not sufficient for access;
9. security regression tests must remain green when adapters are added, removed or reorganized.

## Deployment principles

Production deployments should verify that:

- the primary and isolation services use the intended shared security configuration;
- application listeners remain private behind the reverse proxy;
- direct unsigned isolation access is rejected;
- signed isolated content works only in the intended framing context;
- browser sandbox and CSP restrictions remain active;
- advertising/analytics stripping remains effective for supported sources;
- the full security regression suite passes before traffic is switched.

Exact production paths, secrets, port assignments, signing formats and timing values belong in deployment configuration rather than this public architecture document.

## Known limitations

Some legacy third-party applications require permissive script behavior within the isolated document. This is tolerated only because they remain separated from the primary origin and constrained by browser sandboxing.

The primary application's CSP can be tightened further as legacy inline assets are removed. Storage limits are application-level safeguards rather than a replacement for operating-system or filesystem quotas.
