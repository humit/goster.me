# Contributing to goster.me

goster.me intentionally keeps the public interface small and dependency-light.
The goal is to make visual, frontend and adapter contributions possible without
requiring contributors to understand the whole application.

## Public UI structure

- `static/product.css` — visual design, spacing, typography and design tokens
- `static/product.js` — small progressive-enhancement behaviors such as copy/share
- `product_app.py` — public routes, short links, QR and HTML structure
- `public_app.py` — mature content rendering behavior
- `adapters.py` — source detection and content extraction
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

## Styling

Use the CSS custom properties at the beginning of `static/product.css` as design
tokens. Prefer changing or extending those tokens instead of scattering literal
colors, spacing values and radii throughout the stylesheet.

No CSS framework is required. This is deliberate: a designer should be able to
prototype a new visual skin by editing one ordinary CSS file.

## JavaScript

Keep JavaScript progressive and optional where possible. Core content must remain
reachable without a large client-side application bundle. Browser-specific APIs
must have fallbacks; local/LAN HTTP testing is a supported development workflow.

## Dependencies

New dependencies should earn their place. Prefer small, focused libraries for
well-defined problems over broad application frameworks.

## Tests

At minimum before submitting a change:

```sh
python3 -m unittest -v test_shortlinks.py
python3 -m py_compile product_app.py public_app.py adapters.py shortlinks.py
```

For UI changes, test at least one narrow mobile viewport and one desktop viewport.
