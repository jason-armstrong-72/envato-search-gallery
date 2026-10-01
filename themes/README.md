# Themes

The gallery's look is Jason Armstrong's design system (display name JA), and nothing else. The page
holds no colours, sizes, fonts or spacing of its own. It inlines the skill's `tokens.css` and
`components.css` and is written in the skill's components (`ds-page`, `ds-media-grid`, `ds-media-card`,
`ds-lightbox` and so on). The skill is designed and changed with the
[design-system-creator](https://github.com/jason-armstrong-72/design-system-creator) plugin. Do not edit
its values in this repo.

## Where the build reads it from

1. The installed skill: `$JA_SKILL` if that is set, else `~/.claude/skills/jason-armstrong-design-system`.
   It is used when both `tokens.css` and `components.css` are there.
2. Otherwise the bundled copy in
   [skills/envato-search-gallery/themes/ja/](../skills/envato-search-gallery/themes/ja/), so the plugin
   works when installed alone.

Every build prints one line saying which it used, for example `theme: JA skill at ... (jason-armstrong 2.0.1)`
or `theme: bundled copy in themes/ja ..., because the JA skill is not usable at ...`.

The same folder's `theme.json` is read for three things only: the two Google Fonts links
(`fonts.*.css_url`), and the brand logo's alt text, height and placement. The logo files are embedded in
the page.

The bundled copy is a fallback and has no values of its own. It holds `tokens.css`, `components.css`,
`GENERATED`, `theme.json` and the two logo files (`assets/mark.svg`, `assets/mark-dark.svg`), all copied
byte for byte from the skill.

## Fonts

The page links Hanken Grotesk and IBM Plex Mono from Google Fonts, exactly as the skill's HTML recipe
does. A page opened offline falls back to the system fonts.

## Check and refresh the bundled copy

```bash
python3 skills/envato-search-gallery/scripts/check_theme_sync.py            # is the copy in step?
python3 skills/envato-search-gallery/scripts/check_theme_sync.py --update   # copy the skill's files in
```

- It compares `tokens.css`, `components.css`, `GENERATED`, `theme.json` and the logo files that the
  skill's `theme.json` brand points at, byte for byte, and respects `$JA_SKILL`.
- It prints `in step`, or `behind` with each file that differs. It exits 1 only when a live skill exists
  and differs. With no live skill it says so and exits 0.
- `--update` copies the differing files into `themes/ja/`.
- When the build has to use the bundled copy and a partly present skill differs from it, it prints one
  warning line. It never stops a build.

Run `--update` whenever the skill changes, and commit the result.

The look before the JA theme is at git tag `classic-look`.
