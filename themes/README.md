# Themes

The gallery's look is Jason Armstrong's design system (display name JA). It started from measurements
of <https://www.archetypeai.io/>.

The master theme lives in the `jason-armstrong-design-system` skill (`theme.json`). It is designed and
changed with the [design-system-creator](https://github.com/jason-armstrong-72/design-system-creator)
plugin. Do not edit the values in this repo.

This plugin carries a bundled copy at
[skills/envato-search-gallery/themes/jason-armstrong.json](../skills/envato-search-gallery/themes/jason-armstrong.json),
so it works when installed alone. The copy has its own embedded fonts, its own logo paths and a `sync`
block. Those are the only parts that differ from the master.

## Check and refresh the copy

```bash
python3 skills/envato-search-gallery/scripts/check_theme_sync.py            # is the copy in step?
python3 skills/envato-search-gallery/scripts/check_theme_sync.py --update   # refresh it from the master
```

- The check finds the master at `$JA_THEME_MASTER`, or else at
  `~/.claude/skills/jason-armstrong-design-system/theme.json`.
- It prints `in step`, or `behind` with each value that differs. It exits 1 only when a master exists
  and differs. With no master it says so and exits 0.
- `--update` keeps the plugin-local values (`sync.local_keys`), copies the master's logo files and sets
  `sync.source_version`.
- `build_gallery.py` prints one warning line when the copy is behind the master. It never stops a build.

The original look is at git tag `classic-look`.

## At a glance

| | |
| --- | --- |
| Sans | Hanken Grotesk, weights 200 to 500 (Google Fonts, SIL OFL) |
| Mono | IBM Plex Mono, weights 200 to 500 (Google Fonts, SIL OFL) |
| Ink and page | `#1a1a1a` on `#f1f1f0` (light), `#f1f1f0` on `#000000` (dark) |
| Accent | Forest green `#0d8a4b` (text `#066f33`) light, `#34d399` dark |
| Error and warning | coral `#f4503b` light, `#ff5c48` dark, separate tokens |
| Corners | 1px |

The page has a Light, Dark and System switch. System is the default and follows the display setting.
