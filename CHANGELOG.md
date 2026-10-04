# Changelog

Each release of the plugin gets a section here, newest first. The same notes go on the GitHub
Release for its tag (`v0.9.4` and so on). Versions before 0.9.4 are recorded only in the commit
and pull request history.

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
