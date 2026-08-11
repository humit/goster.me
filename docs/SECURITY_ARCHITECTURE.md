# goster.me Security Architecture

This document defines the security model and invariants for the public goster.me service.
It is intended to remain valid while adapters and rendering code are refactored.

## Security goals

The service accepts URLs supplied by untrusted users and fetches content from third-party
sites. The primary goals are:

1. Never allow a submitted URL to turn goster.me into an SSRF proxy.
2. Never execute third-party HTML or JavaScript with the primary `goster.me` origin.
3. Prefer clean provider embeds over source-page execution.
4. When source-page execution is unavoidable, run it only behind the dedicated sandbox
   origin and browser sandbox restrictions.
5. Fail closed for unknown or unsupported content.
6. Bound storage and process resource consumption.
7. Avoid exposing unnecessary analytics, advertising, server-version or application data.

## Trust boundaries

```text
Internet / submitted URL
        |
        v
+-------------------------+
| URL + redirect security |
| security.py             |
+-------------------------+
        |
        v
+-------------------------+
| adapters / discovery    |
| classify only           |
+-------------------------+
        |
        +---------------- clean embed ----------------+
        |                                              |
        v                                              v
 render_mode=isolate                            render_mode=embed
        |                                              |
        v                                              v
+-------------------------+                    primary shell
| short-link database     |                           |
+-------------------------+                           v
        |                                         provider iframe
        v
primary `goster.me/<code>`
        |
        | short-lived signed capability URL
        v
`s.goster.me/v/<code>?exp=...&sig=...`
        |
        v
third-party HTML/JS in browser sandbox
```

The dedicated sandbox origin is a security boundary, not a cosmetic subdomain. The short
hostname `s.goster.me` is only a name; security does not depend on obscurity.

## URL and network security

`security.py` owns URL/network validation. Adapters must not implement weaker parallel
fetch logic.

Current rules include:

- HTTP and HTTPS only.
- Hostname required.
- Credentials in URLs rejected.
- Raw IPv4/IPv6 literals rejected.
- Non-standard ports rejected.
- URL length bounded.
- Redirect destinations validated before they are opened.
- Adapter fetches use explicit host allowlists.
- YouTube IDs are strictly validated.

Unknown content must result in a generic public error rather than falling back to remote
HTML execution.

## Rendering policy

Rendering modes are deliberately few and explicit.

### Clean embeds

If a provider exposes a clean embed URL, use it instead of source-page isolation.
Examples include YouTube and Wordwall.

### Isolated native content

Some educational sites implement activities directly in their source page and provide no
clean embed. An adapter may classify these as:

```text
render_mode = isolate
selector = <known activity root>
```

Adapters only identify the content and activity root. They do not grant additional browser
privileges.

## Sandbox origin

Third-party source HTML is served only from `s.goster.me`, never from the primary origin.

The sandbox service:

- binds to loopback behind Caddy;
- opens the short-link SQLite database read-only;
- only serves live records whose `render_mode` is `isolate`;
- does not increment access counters or mutate storage;
- fetches source HTML through the same redirect/host validation as the primary service;
- strips known analytics/advertising execution blocks before browser parsing;
- emits `Cache-Control: no-store`;
- hides Python version information;
- exposes no general resolver, static-file or write endpoint.

### Signed capability URLs

A bare URL such as:

```text
https://s.goster.me/v/abc346
```

is not sufficient to access sandbox content.

The primary service generates a short-lived HMAC-SHA256 capability URL:

```text
https://s.goster.me/v/abc346?exp=<unix-time>&sig=<hmac>
```

The signature binds the short code and expiry time. The sandbox rejects missing, invalid,
expired, duplicated or unexpected query parameters. Capability lifetime is bounded to ten
minutes.

Both services use the same secret from:

```text
GOSTER_SANDBOX_SIGNING_KEY
```

The key must contain at least 32 bytes and must not be committed to the repository.
The primary service fails closed if it cannot sign an isolate URL.

A signed URL is a bearer capability. Someone who obtains a valid URL can replay it until it
expires. The purpose is to prevent direct guessing/enumeration and accidental exposure of
bare sandbox routes, not to authenticate end users.

### Browser-level sandbox

The primary page embeds sandbox content with an iframe sandbox that intentionally omits
`allow-same-origin`:

```text
sandbox="allow-scripts allow-modals allow-pointer-lock allow-presentation"
```

Do not add `allow-same-origin` without a separate security review.

The sandbox response also emits a CSP sandbox directive and restricts framing to the
primary origin:

```text
frame-ancestors https://goster.me
sandbox allow-scripts allow-modals allow-pointer-lock allow-presentation
object-src 'none'
form-action 'none'
```

The sandbox must not emit `X-Frame-Options: DENY`, because legitimate cross-origin framing
by `goster.me` is required.

When browsers send `Sec-Fetch-Dest`, the sandbox only accepts `iframe`. This prevents normal
top-level browser navigation. This header is defense-in-depth only; the HMAC capability is
the authorization control because arbitrary HTTP clients can forge request headers.

## Primary-origin policy

The primary origin owns product UI, short links, share/QR controls and clean embed shells.
It must never serve third-party source HTML or JavaScript as same-origin content.

The primary service emits security headers and Caddy applies the public CSP and removes
backend-identifying headers.

The current primary CSP is transitional because legacy rendering still contains inline
scripts/styles. A future hardening pass should move these to external files or use
nonces/hashes so `unsafe-inline` can be removed.

## Privacy filtering

Isolation protects the primary origin, but third-party analytics and advertising are also
unnecessary for the product goal. Before isolated HTML reaches the browser, known execution
blocks for Google Tag Manager, Google Analytics, AdSense/Google Syndication and DoubleClick
are removed.

This is a hygiene/privacy layer, not the main security boundary. The browser sandbox and
origin separation remain mandatory even if filtering is expanded.

## Storage controls

Short-link storage uses defense-in-depth limits:

- maximum row count;
- lower target row count for LRU trimming;
- per-payload UTF-8 byte limit;
- SQLite `max_page_count` applied on every application SQLite connection;
- periodic maintenance for expiry and trimming.

SQLite `max_page_count` is a connection/runtime guard. It is not a persistent database
header setting and is not an operating-system filesystem quota.

Automatic `VACUUM` is intentionally avoided in maintenance because it can temporarily
increase disk and I/O usage.

## Process isolation and resource limits

Systemd units use loopback listeners and restrictive service settings including:

- dedicated non-root `gosterme` user;
- `NoNewPrivileges=true`;
- `ProtectSystem=strict`;
- `ProtectHome=true`;
- capability bounding set removed;
- private temporary/device namespaces;
- kernel/control-group protections;
- address-family restrictions;
- memory, task, file-descriptor and CPU limits.

The sandbox unit has read-only access to `/var/lib/goster.me`.

## Reverse proxy / DNS

Public TLS terminates at Caddy. Application listeners remain on `127.0.0.1`.

Expected public routing:

```text
goster.me    -> Caddy -> 127.0.0.1:8090
s.goster.me  -> Caddy -> 127.0.0.1:8092
```

Only Caddy should be reachable from the Internet. Ports 8090/8092 must not be exposed by
firewall/security-group rules.

## Security invariants for adapter refactors

Adapter modularization must preserve these invariants:

1. Adapters classify/discover content; they do not bypass centralized URL validation.
2. Clean embeds are preferred to source-page isolation.
3. Unknown content fails closed.
4. `render_mode=isolate` is rendered only through the dedicated sandbox origin.
5. Third-party HTML/JS is never served from `goster.me`.
6. Sandbox iframe privileges never include `allow-same-origin`.
7. Sandbox records are read-only and must be live isolate records.
8. Bare sandbox short codes are not public capabilities; a valid short-lived signature is
   required.
9. Security tests must remain green before site adapters are added, removed or reorganized.

## Deployment checklist

Before enabling the sandbox publicly:

1. Generate a strong signing key, for example:

   ```bash
   openssl rand -hex 32
   ```

2. Store it only in `/etc/goster.me/gosterme.env`:

   ```text
   GOSTER_SANDBOX_SIGNING_KEY=<generated-secret>
   GOSTER_SANDBOX_ORIGIN=https://s.goster.me
   ```

3. Ensure both main and sandbox services read the same environment file.
4. Confirm 8090 and 8092 listen only on loopback.
5. Validate and reload Caddy before changing the main service entrypoint.
6. Confirm a bare sandbox `/v/<code>` returns 404.
7. Confirm an invalid/expired signature returns 404.
8. Confirm a signed iframe URL returns 200.
9. Confirm browser top-level navigation to a signed sandbox URL is rejected when
   `Sec-Fetch-Dest: document` is present.
10. Confirm CSP has no `allow-same-origin` sandbox privilege.
11. Confirm known advertising/analytics script URLs are absent from isolated output.
12. Run the full regression suite.

## Known limitations and future work

- Signed sandbox URLs are replayable until their short expiry.
- The sandbox CSP permits broad HTTPS dependencies because native educational apps may rely
  on external assets. Per-adapter dependency allowlists could tighten this later.
- `unsafe-inline` / `unsafe-eval` may be necessary for legacy third-party native apps inside
  the sandbox. These permissions are acceptable only because the document is origin-separated
  and browser-sandboxed.
- The primary CSP should eventually remove `unsafe-inline` after UI scripts/styles are
  externalized or nonce/hash based.
- Storage byte limits are application/SQLite controls rather than filesystem quotas.
