# Adapter refactor plan

Tracks #9.

## Why

`adapters.py` currently owns several distinct responsibilities at once:

- shared adapter/result/error types;
- URL/host normalization and HTML fetching/cache;
- HTML fingerprint parsers;
- provider/site-specific adapters;
- adapter ordering/registration;
- top-level resolution and matching APIs.

`adapter_extensions.py` additionally monkeypatches one site adapter at import time. The goal is to improve ownership and maintainability without changing resolver semantics or weakening centralized security.

## Current compatibility boundary

The refactor must preserve the current public Python surface until callers are migrated deliberately.

### `public_app.py`

Imports these names directly from `adapters`:

- `AdapterError`
- `ResolvedContent`
- `fetch_html`
- `hostname`
- `resolve_url`

This makes `adapters.py` a compatibility API, not merely an implementation file.

### `product_app.py`

Imports `adapters` as a module and depends on implementation-level symbols for the current hardening layer, including:

- `fetch_html`
- `YouTubeAdapter.video_id`
- `UnsupportedURL`

It captures original functions/classes and installs hardened behavior at import time. Extraction must therefore preserve object/function identity expectations until the hardening integration is redesigned explicitly.

### `platform_app.py`

Imports `adapter_extensions` solely for its side effect. It also relies on `product_app`'s captured original resolver to retain the hardened network path while allowing sandbox-backed isolate results.

This temporary layering is security-sensitive and must not be casually reordered.

### Tests / CLI tools

Existing tests and repository helper commands import or invoke the current adapter module directly. These form part of the compatibility surface during migration.

## Current registry

Adapter order is behaviorally significant:

1. `YouTubeAdapter`
2. `WordwallDirectAdapter`
3. `GenericWordwallPageAdapter`
4. `IlkokulAkademiGithubEmbedAdapter`
5. `IlkokulAkademiNativeAdapter`
6. `IlkOkulNativeAdapter`
7. `TestSaatiZombifyAdapter`

The current design intentionally prefers clean embeds before source-page isolation. The modular registry must preserve this ordering unless a separate behavior-change issue explicitly changes it.

## Proposed package boundary

Use `goster_adapters/` rather than `adapters/` during migration to avoid Python module/package ambiguity with the existing `adapters.py` compatibility facade.

Target direction:

```text
goster_adapters/
    __init__.py
    types.py
    registry.py
    network.py
    parsers.py
    providers/
        youtube.py
        wordwall.py
    sites/
        ilkokulakademi.py
        ilk_okul.py
        testsaati.py

adapters.py          # compatibility facade during migration
adapter_extensions.py # removed after İlk-Okul migration owns all fingerprints
```

The exact file split may be adjusted as extraction reveals coupling, but these ownership boundaries should remain explicit.

## Security boundary

The refactor must not create a second network/security implementation.

Current production hardening wraps adapter network behavior from `product_app.py`/`security.py`. Until that integration is simplified deliberately:

- extracted adapters must continue to flow through the same hardened fetch path;
- no site module may introduce raw `urlopen`/requests-style fetching;
- redirect/SSRF/public-URL policy remains centralized;
- isolate behavior and sandbox authorization remain unchanged;
- unknown/unsupported content continues to fail closed.

## Migration increments

### Increment 1 — inventory and contract

- document imports/callers and registry order;
- define compatibility facade requirement;
- define initial package ownership;
- no runtime behavior changes.

### Increment 2 — shared primitives

- introduce `goster_adapters.types` and registry primitives;
- keep `adapters.py` re-exporting the old names;
- preserve current `ADAPTERS`, `resolve_url`, and `matching_adapters` behavior;
- prove object/result parity with focused tests.

### Increment 3 — first provider family

Move a low-coupling provider family (likely YouTube) behind the facade first. Preserve the current hardening hook for `YouTubeAdapter.video_id` or replace it only with an equivalent explicitly tested boundary.

### Increment 4 — embed adapters

Move Wordwall and other clean-embed discovery while preserving embed-before-isolate ordering.

### Increment 5 — native site adapters

Move native site families incrementally. `IlkOkulNativeAdapter` migration must absorb the fast-reading fingerprints currently installed through `adapter_extensions.py`.

### Increment 6 — remove monkeypatch extension

Delete `adapter_extensions.py` only after its behavior has a normal owner and platform startup no longer depends on side-effect registration.

### Increment 7 — simplify integration

Only after parity is established, consider reducing implementation-level coupling from `product_app.py` to adapter internals. This is a separate riskier cleanup step, not a prerequisite for modularization.

## Relationship to supported-sites catalog (#11)

The explicit registry should become the canonical source from which supported-site/provider metadata can be derived or validated. Do not create an unrelated second manually-maintained adapter registry merely for the public catalog.

Provider/site metadata should eventually be close to registration and be sufficient to render the Turkish-primary / English-secondary supported-sites view and inclusion/exclusion policy without exposing unnecessary implementation details.

## Definition of done for this refactor

- adapter ownership is obvious from repository structure;
- `adapters.py` compatibility surface remains stable until callers are explicitly migrated;
- registry order and resolver behavior are preserved;
- `adapter_extensions.py` is removed without losing fast-reading support;
- no weaker or parallel network/security path exists;
- existing regression suite remains green throughout;
- representative real URLs pass exact-SHA staging validation;
- supported-sites catalog work can consume/validate registry metadata without duplicate truth sources.
