# Contributing to goster.me

goster.me intentionally keeps the public interface small, lightweight and low-dependency.
The goal is to let designers, frontend contributors and adapter developers work on
their area without requiring everyone to understand the whole application.

Turkish version: [CONTRIBUTING.md](CONTRIBUTING.md)

## Public UI structure

- `static/product.css` — visual design, spacing, typography and design tokens
- `static/product.js` — small progressive-enhancement behaviors such as copy/share
- `product_app.py` — public routes, short links, QR and HTML structure
- `public_app.py` — mature content-rendering behavior
- `adapters.py` — source detection and extraction of the actual content
- `shortlinks.py` — persistent short-link storage and expiry

## Design principles

The interface should practice the same content-minimization principles that the
product applies to source websites:

- content before chrome;
- minimal motion;
- no decorative UI without a purpose;
- readable typography and comfortable contrast;
- mobile-first controls;
- semantic HTML and keyboard-accessible actions;
- no tracking or third-party assets merely for presentation;
- respect `prefers-reduced-motion` when motion is introduced.

The goal is not to build a SaaS landing page. It is to build a calm, understandable
and trustworthy tool.

## Styling / CSS

Use the CSS custom properties at the beginning of `static/product.css` as design
tokens. Prefer changing or extending those tokens instead of scattering literal
colors, spacing values and radii throughout the stylesheet.

No CSS framework is required. This is deliberate: a designer should be able to
prototype a new visual skin by editing one ordinary CSS file without learning the
Python or adapter architecture.

## JavaScript

Keep JavaScript progressive where possible. Core content must remain reachable
without a large client-side application bundle.

Browser-specific APIs must have fallbacks. Local/LAN HTTP development is a supported
workflow; secure-context APIs such as Clipboard and Web Share must not cause the UI
to fail silently when unavailable.

## Adapter contributions

Adapters are the core function of the project. When adding a new site or content type:

1. start from real URLs seen in actual use;
2. prefer explicit fingerprints over broad scraping;
3. preserve fail-closed behavior so the wrong content is not exposed;
4. verify representative URLs with `test-adapter`;
5. rerun corpus analysis when appropriate.

## Dependencies

New dependencies should earn their place. Prefer small, focused libraries for
well-defined problems over broad application frameworks.

## Tests

At minimum before submitting a change:

```sh
python -m unittest -v test_shortlinks.py
python -m py_compile product_app.py public_app.py adapters.py shortlinks.py
```

For UI changes, test at least one narrow mobile viewport and one desktop viewport.
For adapter changes, also validate the relevant real-world URL examples.
