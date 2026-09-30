# Themes

Design reference for the gallery page's themes. The theme itself lives with the skill, in
[skills/envato-search-gallery/themes/](../skills/envato-search-gallery/themes/), so it travels when the
skill folder is copied on its own, and `build_gallery.py` reads it (`--theme NAME|PATH`). This
folder keeps the tuner page the theme was designed on.

## archetype

A near-monochrome theme with one coral accent, derived from <https://www.archetypeai.io/>.

- [archetype.json](../skills/envato-search-gallery/themes/archetype.json): every locked value (type roles, colour in light and dark,
  spacing, shape, interaction states, components) plus the accepted trade-offs and what is still open.
- [reference/tuner.html](reference/tuner.html): the page the theme was designed on. Open it in a
  browser and use **Tune** for controls on every value, with a light and dark switch. **Copy
  settings** exports the current values as text. The Envato preview images are grey placeholders
  on purpose, because previews are for review only and must not be committed.

### At a glance

| | |
| --- | --- |
| Sans | Hanken Grotesk, weights 200 to 500 (Google Fonts, SIL OFL) |
| Mono | IBM Plex Mono, weights 200 to 500 (Google Fonts, SIL OFL) |
| Ink and page | `#1a1a1a` on `#f1f1f0` (light), `#f1f1f0` on `#000000` (dark) |
| Accent | coral `#ff5c48` |
| Corners | 1px |

The reference site uses PP Neue Montreal, which is a paid font. The two Google fonts are close
stand-ins. The site has no dark mode, so the dark theme is derived.

### Colour mode switch

Light, Dark and System as three icon buttons (sun, moon, monitor). System is the default and follows
the display setting. The choice is remembered in the browser.

### Spacing scale

Spacing sits on a scale named `size-N` (4, 8, 12, 16, 20, 24, 32, 40, 48, 56, 64 px). Layout measures
and corner radii are deliberately off it. The tuner's Snap button snaps any tuned values to the scale
and tags anything off it.

### Interaction states

- **Button:** outlined at rest, solid on hover or keyboard focus, arrow coral throughout.
- **Chip and pill:** coral border, text and a tint fill on hover (8% light, 16% dark). Static in the
  gallery; add class `is-action` to make one interactive, and `pill` for fully round ends.
- **Toggle:** coral at rest, ink on hover, coral and underlined when pressed.

### Components

Input, select, table, callouts, code, modal, the empty, loading and error states, tabs, tooltip,
toast, pagination, navigation and a date picker are specified in `components` and shown at the
bottom of the tuner page.

### Accessibility

Measured in a browser on 2026-09-30 and recorded under `accessibility` in
[archetype.json](../skills/envato-search-gallery/themes/archetype.json). Four fixes are applied (subtle grey, edges of interactive chips and
pagination, an ink focus ring on light, and 24px/44px control sizes). What remains: coral small text
on the light page, which is accepted. The tuner's Touch
switch previews the 44px targets.

### Known trade-offs

Coral small text on the light page is 2.7:1, under the 4.5:1 target. It was accepted, and coral is
used for shapes and interaction cues. See `accepted_debt` in [archetype.json](../skills/envato-search-gallery/themes/archetype.json).
