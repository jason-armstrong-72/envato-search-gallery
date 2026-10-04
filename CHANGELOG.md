# Changelog

Each release of the plugin gets a section here, newest first. The same notes go on the GitHub
Release for its tag (`v0.9.4` and so on). A change is listed under the version that first carried it
on `main`.

When a release changes the version in `.claude-plugin/plugin.json`, add its section in the same pull
request. After it merges, tag the merge commit and publish a GitHub Release with the same notes.

## 0.9.4 (2026-10-04)

### Fixes

- Gallery pages load the JA body font again. Since the JA skill moved to schema 4, pages loaded only
  the mono font, and body text fell back to Helvetica Neue. The gallery now links the heading, body
  and mono fonts the theme has, and still reads a schema 3 theme's `sans` font (#42, #43).

### Bundled theme

- The bundled copy of the JA design system in `themes/ja/` is updated from 2.1.0 to 3.0.0
  (design-system-creator 0.11.0). It now has schema 4 fonts, keeps the switch visible in forced
  colours, and drops the `--font` and `--mono` aliases. The gallery uses this copy only when the
  JA skill isn't installed (#41, #43).

## 0.9.3 (2026-10-02)

### Bundled theme

- The bundled copy of the JA design system in `themes/ja/` is updated to JA 2.1.0
  (design-system-creator 0.10.0) (#40).

## 0.9.2 (2026-10-01)

### Bundled theme

- The bundled copy of the JA design system in `themes/ja/` is refreshed from the design-system-creator
  0.9.0 export. The only change is `aria-invalid` styling, which the gallery doesn't use, so pages
  look the same (#38).

## 0.9.1 (2026-10-01)

### Gallery

- The results line and the footer use the JA skill's `ds-muted` style. The counts in the results
  line ("4 results") are now muted like the rest of the line instead of full-strength. The gallery
  no longer has any CSS of its own beyond the JA recipe's body rules (#37).

### Bundled theme

- The bundled copy of the JA design system is refreshed from the design-system-creator 0.8.1
  export (#37).

## 0.9.0 (2026-10-01)

### Gallery

- Breaking: the gallery is rebuilt on the JA design system skill. Every page inlines `tokens.css`
  and `components.css` from the installed `jason-armstrong-design-system` skill, or from the folder
  in `$JA_SKILL`. If the skill isn't installed, it uses a bundled copy of those files in
  `themes/ja/`. The build prints which one it used (#36).
- Breaking: the `--theme` option, the `jason-armstrong.json` theme copy, the layout file and the
  gallery's own CSS and variables are removed. The page is made of JA components only (#36).
- Fonts are now linked the way JA links them instead of embedded, so a page drops from about 193 KB
  to 59 KB. A page opened offline uses system fonts (#36).
- What looks different: JA's page padding, the theme switch sits in the header, filters are an
  accordion of chips, bylines use uppercase label type, buttons have no arrows, and the lightbox
  follows the light or dark mode with a backdrop the page faintly shows through (#36).
- The saved light or dark choice is now stored under a new key, so a saved choice resets once (#36).

### Theme sync

- `check_theme_sync.py` now compares the bundled JA files with the live skill file by file, and
  `--update` refreshes them (#36).

## 0.8.2 (2026-10-01)

### Bundled theme

- The bundled theme copy is refreshed to JA 2.0.1. The only change is a description, so pages look
  the same (#34).

## 0.8.1 (2026-10-01)

### Gallery

- A page writes only the colour variables it reads, so `--accent`, `--error` and `--warning` are no
  longer in the built page. Colours on the page are unchanged (#32).

### Docs

- The themes README separates error and warning, and notes that the page uses neither (#32).

## 0.8.0 (2026-10-01)

### Gallery

- A page writes only the type and spacing variables it reads, and the small-screen type rule only
  for the roles it uses (#29).
- The builder can read a local image (a path relative to the input file, or a `file://` link). An
  offline test input with placeholder images is added, and `example-input.json` no longer crashes
  the builder (#29).

### Local server

- Old pages are also pruned when the gallery server starts, not only on each build. Pruning removes
  only pages the builder made, so other files in the gallery folder are left alone (#28, #31).

### Theme sync

- `check_theme_sync.py` also compares the logo files with the master's, and `--update` copies them
  (#28).

## 0.7.0 (2026-10-01)

### Bundled theme

- Breaking: the bundled theme copy is updated to JA 2.0.0, and the builder now reads only schema 3
  themes. A schema 2 theme stops the build with a message (#25).
- The gallery's own values that schema 3 took out of the brand theme (the button arrow, three type
  roles, 17 spacing entries and the lightbox backdrop) move into a new
  `themes/jason-armstrong.layout.json`, which the builder merges beside the theme. Pages look the
  same (#25).

## 0.6.2 (2026-10-01)

### Bundled theme

- The bundled theme copy is refreshed to JA 1.4.0. The warning colour is now deep amber (#24).

## 0.6.1 (2026-09-30)

### Gallery

- The phone type sizes also apply on a phone held sideways (#23).
- Phones held sideways no longer enlarge some text blocks by themselves, such as the filter heading
  and the footer note (#23).

## 0.6.0 (2026-09-30)

### Gallery

- Type is larger on phones: on screens up to 600px wide, small type grows by 2px and the largest
  type comes down to 48px (#21).
- The filter toggles draw their own open and closed arrow, which was missing on touch screens (#21).
- Hover styles apply only on devices that can hover, so a tapped filter toggle no longer keeps its
  hover colour on a touch screen (#21).
- The gallery title takes the theme's size at every width, 64px on desktop and 48px on a small
  screen, and shrinks only when a single word is too wide for the line (#21).

### Bundled theme

- The bundled theme copy is refreshed to JA 1.3.0 (#21).

## 0.5.1 (2026-09-30)

This version was set on a branch and never released by itself. Its change reached `main` with
0.6.0 (#21).

## 0.5.0 (2026-09-30)

### Bundled theme

- Breaking: the bundled theme `archetype` becomes `jason-armstrong`, a copy of the master theme in
  the `jason-armstrong-design-system` skill. The builder reads only schema version 2 themes and stops
  with a message on any other (#17).
- The placeholder brand mark shows above the eyebrow, with its dark-mode file in dark mode (#17).
- Error and warning in light mode are `#f4503b`, and the lightbox colours come from the theme (#17).

### Theme sync

- New `scripts/check_theme_sync.py` says whether the bundled copy is in step with the master, and
  `--update` refreshes it. The builder prints one warning line when the copy is behind (#17).

### Removed

- The hand-built tuner page is removed. The design-system-creator plugin replaces it (#17).
- Stale wording from the coral accent is removed from the theme (#16).

## 0.4.0 (2026-09-30)

### Gallery

- The gallery's look is read from a theme file, `archetype.json`, instead of being written into the
  builder: colour in light and dark, type, spacing, corners and fonts. The old look is kept only at
  the git tag `classic-look` (#13).
- New `--theme NAME|PATH` option picks another theme file (#13).
- Fonts are embedded in the page, including the latin-extended subsets for accented characters, so
  it needs no network (#13).
- Breaking: the accent changes from coral to Forest green, and coral stays as separate error and
  warning colours. The colour tokens are renamed (`coral` and `coraltext` become `accent` and
  `accenttext`) and the builder requires the new ones (#13).
- A theme can set a brand logo, embedded in the page, above the title or top left (#13).
- A Light, Dark and System switch. System is the default and the choice is remembered (#13).

### Local server

- The gallery server tries port 47615 first, so links and the saved light or dark choice survive a
  restart. `ENVATO_GALLERY_PORT` overrides it (#15).

### Fixes

- The lightbox close, previous and next buttons sit where they should. The close button was in the
  middle of the photo (#13).

### Docs

- The Archetype theme is added in `themes/`, with the tuner page it was designed on and its
  accessibility audit (#11, #12).

## 0.3.1 (2026-09-30)

### Fixes

- `SKILL.md` names the `results` key the input file needs, so an agent no longer writes `items` and
  only learns from the script error (#8).

### Docs

- The README describes the local server's lifecycle, what leaves the machine, and how updates are
  applied (#9).

## 0.3.0 (2026-09-30)

### Gallery

- Galleries are served from a shared, localhost-only server instead of opening a `file://` page. The
  server is reused across sessions and exits after an hour with no requests, and has `status` and
  `stop` commands. No browser opens unless you pass `--open`. Galleries older than 7 days are
  deleted (#6).

### Docs

- The README covers installing in other environments, the `/envato-search-gallery:envato-search`
  command, and asking for the skill by name (#2, #4).
- `plugin.json` gains homepage, repository and licence links (#5).

## 0.2.0 (2026-09-30)

### Fixes

- A shorter skill description, so the skill starts on its own in a real session (#3).

### Gallery

- New `envato-search` command to run the skill explicitly (#3).
- The script prints a clickable link to the gallery (#3).

## 0.1.0 (2026-09-30)

- First release: the envato-search-gallery skill, its gallery builder, and the filter reference for
  each asset type (#1).
