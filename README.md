# envato-search-gallery

A Claude skill that turns an Envato Elements search into a quick visual gallery.

The [Envato MCP server](https://elements.envato.com/learn/envato-mcp-server) lets an AI
assistant search the Elements catalogue, but it returns a list of links. This skill sits
between that and a full search on elements.envato.com: the agent runs the search, builds one
HTML page of previews, you scan it, click an image to enlarge it, and follow the link to
Envato to license and download the original.

Unofficial. Not affiliated with or endorsed by Envato.

## What you get

- A single self-contained HTML file (previews embedded, works offline, no server or account).
- Click a thumbnail to enlarge it; arrow keys move between images, Escape closes.
- The filters available for that asset type, and any that were applied, shown as chips.
- A "View on Envato" link on every card.
- Light and dark themes, and it holds together at phone width.

## Limits

- **Search only.** The Envato MCP server cannot download or license assets. You download
  from elements.envato.com, which needs an active Elements subscription. Searching does not.
- Previews are 600px and watermarked, so use them to judge composition, not detail.
- The page is static. To refine a search, ask the agent again.
- Visual asset types only (photos, graphics, templates, video and so on). Music and sound
  effects have no image previews.

## Install

Quick start, in a terminal with [Claude Code](https://claude.com/claude-code) installed:

```bash
claude mcp add --scope user --transport http envato https://mcp.envato.com/mcp
claude plugin marketplace add jason-armstrong-72/envato-search-gallery
claude plugin install envato-search-gallery@envato-search-gallery
```

Then start a new Claude Code session; a session that was already open will not have the skill.

- The first command connects Envato's MCP server. Anonymous is enough: OAuth is optional and
  not needed for search.
- The other two install this skill as a plugin. The plugin install was tested from a clean
  folder against this repo on 2026-09-30.
- Needs `python3` (3.8 or newer). No packages to install.

Update or remove later:

```bash
claude plugin update envato-search-gallery@envato-search-gallery
claude plugin uninstall envato-search-gallery@envato-search-gallery
```

### Other environments

| Where you work | What to do |
| --- | --- |
| Claude Code in a terminal | The quick start above |
| VS Code extension | Nothing extra. The extension shares Claude Code's config, so run the quick start once in any terminal (VS Code's integrated terminal works) and start a new conversation |
| A team repo or CI | Use project scope so the setup travels with the repo, then commit the `.claude/settings.json` it writes (see below) |
| Claude Desktop | Connect the MCP server under Settings, Connectors, as a custom connector with the URL `https://mcp.envato.com/mcp` (OAuth fields empty; custom connectors need a paid plan). This skill has not been tested in Desktop, and Desktop may show the search results inline without it |
| Cursor and other agents | Not tested. The skill is a plain folder: `SKILL.md` instructions, a standard-library Python script and JSON references. Copy `skills/envato-search-gallery` to wherever your agent loads skills or rules from. The agent needs the Envato MCP server and the ability to run Python |
| No agent at all | Run the script on its own (see below) |

Project scope, for a team repo:

```bash
claude plugin marketplace add jason-armstrong-72/envato-search-gallery --scope project
claude plugin install envato-search-gallery@envato-search-gallery --scope project
```

This adds `extraKnownMarketplaces` and `enabledPlugins` entries to the project's
`.claude/settings.json`. The Envato MCP server is added separately (`claude mcp add` has its own
`--scope project` option).

Manual install, without the plugin system:

```bash
cp -R skills/envato-search-gallery ~/.claude/skills/
```

### Using the script on its own

The gallery builder has no dependency on Claude Code. Give it a results file in the format of
[references/example-input.json](skills/envato-search-gallery/references/example-input.json):

```bash
python3 skills/envato-search-gallery/scripts/build_gallery.py results.json
```

Add `--no-open` to write the file without opening a browser (headless machines, CI) and
`--out PATH` to choose where it goes.

## Use

Ask for what you want:

> Search Envato for 10 landscape photos of a compounding pharmacy.

The agent mentions the relevant filters, searches, builds the gallery and opens it. Pick an
image, and it hands you the Envato link.

## Layout

```text
skills/envato-search-gallery/
  SKILL.md                     what the agent does, step by step
  scripts/build_gallery.py     results JSON in, self-contained HTML out (stdlib only)
  references/filters.json      filters per asset type, from the MCP tool schemas
  references/example-input.json
```

## Notes for maintainers

- Preview URLs are signed. Truncating one (dropping the trailing `&s=` token) makes the CDN
  answer "Wrong signature"; the script reports that case in plain words.
- `references/filters.json` was written from the tool schemas on 2026-09-30. Envato may add
  or change filters; the file needs refreshing when they do.
- Previews are for review. Do not commit or redistribute them; Envato's licence terms apply
  to the originals. The gallery leaves the watermark untouched, which matters: Envato's terms
  prohibit removing watermarks or protective markings, previews included. Read Envato's
  current terms yourself before relying on this; the help centre blocks automated fetching,
  so they were not checked in full when this was written.
