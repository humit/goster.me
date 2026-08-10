# goster.me

**Don't show me anything I don't need.**

goster.me starts from a simple idea: the content we want on the web is not the same
thing as the advertising, recommendations, autoplay, engagement mechanics, confusing
navigation and visual clutter wrapped around it.

Watching a video, playing a game, completing homework or opening an activity should
not require accepting an entire source platform's attention economy along with it.
This matters especially for children.

> **Accessing content does not mean consenting to the attention economy around it.**

The domain name carries the Turkish product message itself. `goster.me` reads as
"gösterme" — "don't show [it]" — and supports lines such as:

- Don't show me ads.
- Don't show my child distracting things.
- Don't show me a chaotic page.
- Show the video. Don't show YouTube.
- Show the content. Don't show the rest.

## What it does

A user gives goster.me an ordinary web URL. The resolver and adapter layer identifies
the part that is actually wanted, and the renderer exposes only that content whenever
it can do so safely.

```text
long / cluttered source URL
        |
        v
resolver + content adapter
        |
        +-- YouTube --------> contained video
        +-- Wordwall -------> clean embed
        +-- native exercise -> isolated application
        +-- collection -----> clean activity list
        +-- unknown --------> fail closed / review
        |
        v
goster.me/k7p3mx
```

Public short links are designed to be readable, speakable and easy to enter on a
second device. The short-code alphabet excludes commonly confused characters such as
`0/O`, `1/I/l`, `2/Z` and `5/S`.

The current default lifetime is 14 days and can be changed with
`GOSTER_LINK_TTL_SECONDS`. Short links are persisted in SQLite, so service restarts do
not invalidate them.

## Design principles

- Put the real content first; the goster.me interface should not compete for attention.
- Do not expose unnecessary source-site navigation to children or end users.
- Preserve interactive applications when their JavaScript depends on the original DOM.
- Prefer clean provider embeds when available.
- Use explicit adapter fingerprints rather than broad, fragile scraping.
- Fail closed when content cannot be identified safely.
- Keep media acquisition separate from presentation.
- Use the real teacher/parent URL corpus as the compatibility benchmark.
- Keep goster.me identity, back, copy and share controls visible and consistent in clean views.

## Short-link model

The public canonical form is:

```text
https://goster.me/k7p3mx
```

The earlier `/g/<id>` prototype route may remain as a compatibility route during the
transition, but URLs shown, copied and shared with users should use the canonical short
form.

The short-link store lives in `shortlinks.py`. Its default database path is:

```text
/var/lib/goster.me/goster.sqlite3
```

Override it with:

```bash
export GOSTER_DATABASE=/path/to/goster.sqlite3
```

## Public application

`product_app.py` adds the public product shell without rewriting the existing adapter
and renderer implementation:

- minimal manifesto-led landing page;
- one quiet example slogan selected per page load;
- persistent human-friendly short URLs;
- canonical `/<short-code>` routes;
- branded viewer toolbar;
- copy/share actions;
- expired-link handling.

Run it with:

```bash
python3 product_app.py
```

Bind settings can be configured through the environment:

```bash
GOSTER_HOST=127.0.0.1 GOSTER_PORT=8090 python3 product_app.py
```

## Childsafe and Childsafe Inbox

The project originated from the need for a more controlled web experience for
children. That use case continues under the **Childsafe** concept.

**Childsafe Inbox** is the specific parent/teacher ingestion workflow that takes shared
links into local media and Jellyfin. The public goster.me product can reuse the same
adapter knowledge, but it is not limited to Jellyfin or to child-only content.

## Render modes

### `embed`

When a source already exposes a clean provider URL, only the activity is embedded.

```text
source page
    -> adapter discovers provider URL
    -> goster.me embeds only the activity
```

### `isolate`

When an interactive application depends on the source page's own DOM and JavaScript,
goster.me keeps the document intact and visually isolates the application root instead
of extracting and breaking it.

```text
source page
    -> adapter identifies application fingerprint
    -> selector is returned
    -> renderer hides unrelated page content
```

## Current adapter families

The proof of concept currently covers content families including:

- YouTube;
- Wordwall embeds;
- Wordwall activities embedded in education sites;
- TestSaati Zombify quizzes;
- İlkokul Akademi native interactive exercises;
- trusted GitHub Pages exercise embeds;
- additional controlled education-site adapters derived from the real URL corpus.

New providers are added based on URLs observed in real use.

## Important files

`product_app.py`
: Public goster.me product shell and canonical short-link routes.

`public_app.py`
: Existing public renderer and adapter integration.

`shortlinks.py`
: SQLite short-link persistence, human-friendly code generation and TTL handling.

`app.py`
: Childsafe Inbox web service.

`adapters.py`
: URL matching, content resolution and adapter implementations.

`test-adapter`
: Resolve and inspect a single URL.

`analyze-corpus`
: Analyze a WhatsApp/chat URL corpus against all adapters.

## Test

Short-link behavior can be tested with the Python standard library:

```bash
python3 -m unittest -v test_shortlinks.py
```

For adapter development, validate representative URLs with `test-adapter` and run a
full corpus regression before milestones.

## Security model

goster.me is not an unrestricted web proxy. Its core approach is **content
minimization**: preserve what the user asked for while avoiding unnecessary source
platform navigation, cross-promotion and attention surfaces.

Unknown or unsafe-to-resolve content should remain unresolved until there is a
controlled fallback or suitable adapter.

Public deployment still requires explicit consideration of authentication, abuse/rate
limiting, storage cleanup and provider-specific security policies.

---

Türkçe dokümantasyon: [README.md](README.md)
