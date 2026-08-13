# Theme contract

goster.me uses one semantic color system across the home, information,
feedback, error, share, and first-party viewer-control surfaces. Layout and
component rules must consume the `--g-*` tokens in `static/product.css` rather
than introducing page-specific palettes.

## Operational selection

The active theme is selected explicitly with `GOSTER_THEME`:

```text
default
april-23
new-year
november-10
```

Unknown values fail safely to `default`. Theme selection is server-wide and
requires the application services to be restarted after the environment value
changes. It is deliberately not date-driven: a deployment should never change
public presentation automatically because of server time, timezone, or a
calendar assumption.

The optional presets are intentionally restrained color treatments. They add
no images, remote fonts, scripts, requests, animation, layout changes, or
provider privileges.

## Token layers

The canonical tokens are defined in `static/product.css`:

- page: `--g-bg`, `--g-surface`, `--g-surface-soft`, `--g-border`;
- content: `--g-text`, `--g-muted`;
- interaction: `--g-accent`, `--g-accent-hover`, `--g-accent-ink`,
  `--g-accent-text`, `--g-accent-text-hover`, `--g-focus`;
- state: `--g-danger`, `--g-success`;
- viewer overlay: `--g-viewer-panel`, `--g-viewer-control`,
  `--g-viewer-control-hover`, `--g-viewer-control-border`,
  `--g-viewer-text`, `--g-viewer-muted`.

Legacy variable aliases remain temporarily because the older renderer is still
loaded before the product stylesheet. New components must use only `--g-*`
tokens. Removing those aliases belongs to the separate legacy-style/CSP
cleanup, not to an individual theme.

## Adding a theme

1. Add its allowlisted name and light/dark browser colors to
   `THEME_META_COLORS` in `product_app.py`.
2. Add light and dark token overrides under the matching
   `:root[data-theme="..."]` selectors in `static/product.css`.
3. Keep every normal-size text/background and text/accent pair at WCAG AA
   contrast (`4.5:1` or better).
4. Do not add component, layout, provider, or adapter rules to a theme block.
5. Run the theme contract and full regression suites, then visually check the
   home, about, contact, unsupported, share, clean-embed, and isolated viewer
   pages in light and dark modes.

Seasonal artwork is outside the default contract. If later justified, it must
remain first-party, optional, size-budgeted, non-blocking, motion-safe, and
decorative-only so the product's content-minimization purpose remains primary.
