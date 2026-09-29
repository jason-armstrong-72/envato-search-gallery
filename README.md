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

## Setup

1. **Connect the Envato MCP server** (anonymous is enough; OAuth is optional and not needed
   for search).

   Claude Code:

   ```bash
   claude mcp add --scope user --transport http envato https://mcp.envato.com/mcp
   ```

   Claude Desktop: Settings, Connectors, add a custom connector with the URL
   `https://mcp.envato.com/mcp`. Leave the OAuth fields empty.

2. **Install the skill.**

   As a plugin (untested from a remote source until this repo is published):

   ```text
   /plugin marketplace add jason-armstrong-72/envato-search-gallery
   /plugin install envato-search-gallery@envato-search-gallery
   ```

   Or copy the folder by hand:

   ```bash
   cp -R skills/envato-search-gallery ~/.claude/skills/
   ```

3. Needs `python3` (3.8 or newer). No packages to install.

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
