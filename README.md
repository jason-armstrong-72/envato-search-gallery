# envato-search-gallery

A Claude skill that turns an Envato Elements search into a quick visual gallery.

The [Envato MCP server](https://elements.envato.com/learn/envato-mcp-server) lets an AI
assistant search the Elements catalogue, but it returns a list of links. This skill sits
between that and a full search on elements.envato.com: the agent runs the search, builds one
HTML page of previews, you scan it, click an image to enlarge it, and follow the link to
Envato to license and download the original.

Unofficial. Not affiliated with or endorsed by Envato.

## What you get

- A single self-contained HTML file (previews embedded, no account), served on a local
  `http://localhost` link so the chat can hand you a clickable link.
- Click a thumbnail to enlarge it; arrow keys move between images, Escape closes.
- The filters available for that asset type, and any that were applied, shown as chips.
- A "View on Envato" link on every card.
- A Light, Dark and System switch (System follows the display setting, and the choice is
  remembered), and it holds together at phone width.
- A theme drives the whole look: colour, type, spacing, corners and the fonts. See
  [Themes](#themes).

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

- `claude plugin update` prints "Restart to apply changes". Start a new session, or run
  `/reload-plugins` in the current one to switch hooks, MCP servers and LSP servers to the new
  version without stopping. Anything that runs as a monitor needs a full restart (this plugin
  has none).
- An update is only offered when the version in `.claude-plugin/plugin.json` changes. A change
  that does not bump the version does not reach installed copies.
- To see what is installed, run `claude plugin list` in a terminal. In the VS Code extension's
  chat panel, `/plugins` (plural) opens the Manage plugins dialog.

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
[references/example-input.json](skills/envato-search-gallery/references/example-input.json),
an object whose list of items is under the key `results`:

```bash
python3 skills/envato-search-gallery/scripts/build_gallery.py results.json
```

It writes to `~/.cache/envato-gallery`, starts a local server if one is not already running and
prints `open: http://localhost:PORT/...`. Nothing opens in a browser unless you add `--open`.
`--no-serve` prints a `file://` link instead, and `--out PATH` writes to a path of your choice
(also a `file://` link).

## Use

Ask for what you want:

> Search Envato for 10 landscape photos of a compounding pharmacy.

The agent mentions the relevant filters, searches, builds the gallery and gives you a link to
it. Click it: in VS Code it opens in a side panel, elsewhere in your browser. Pick an image, and
it hands you the Envato link. Galleries live in `~/.cache/envato-gallery` and are deleted after
7 days; use `--out` to keep one.

### The local server

The link is `http://localhost`, served by `scripts/gallery_server.py`, a small
standard-library Python server. It is the only thing this plugin leaves running, so here is
exactly what it does.

#### What it is

- **One server, shared.** Every session and every project reuses it. A new search checks for a
  live server first and only starts one if there is none.
- **Local only.** It listens on `127.0.0.1` and serves one folder, `~/.cache/envato-gallery`,
  so nothing else on your machine or your network can reach it.
- **Nothing to install or approve** beyond Python. Claude Code may ask once to run the
  command; allowlist `python3 *gallery_server.py*` and `python3 *build_gallery.py*` to stop
  that.

#### It cleans up after itself, so there is nothing to manage

- **It does not run forever.** It exits on its own after an hour with no requests (the
  default; `--idle SECONDS` changes it). It checks every 30 seconds or less, then shuts down
  and removes its state file (`.server.json` in the gallery folder).
- **It does not start at login or survive a restart.** It is not a service. It starts when a
  search needs it, and a reboot or a crash simply ends it.
- **A dead server is not a problem.** The next search checks that the recorded process really
  is the gallery server (not a leftover file, and not another program that reused the port)
  and starts a fresh one if not.
- **An open page keeps working.** Each page has its images embedded, so a tab you already have
  open does not need the server. Only opening a page afresh does. The server prefers port 47615
  (set `ENVATO_GALLERY_PORT` to change it), so an old link keeps working after a restart. If that
  port is taken by another program it uses a free one instead, and an old link may stop working;
  ask the agent to search again.
- **Old pages are deleted.** Galleries older than 7 days are removed the next time one is
  built. A three-image gallery is about 250 to 300 KB (about 180 KB of that is the embedded fonts), so a
  machine that stops using the plugin keeps only a few small files.

The shutdown was tested on 2026-09-30 by starting the server with `--idle 60` and confirming
it had exited after about a minute and a half with no requests.

#### If you want it gone sooner

```bash
python3 skills/envato-search-gallery/scripts/gallery_server.py status   # prints the port, or "not running"
python3 skills/envato-search-gallery/scripts/gallery_server.py stop
```

The path is relative to the plugin folder. For a plugin install, that folder is under
`~/.claude/plugins/cache/envato-search-gallery/`.

#### Where it works

- The link works where the browser runs on the same machine as the agent. Over SSH, in a dev
  container or in the Claude web app it will not, and you get a `file://` link or the plain
  list.
- **No Python 3?** Then there is no gallery. The agent checks first and gives a plain list of
  links instead. On macOS the system `python3` is a stub until the developer tools are
  installed, which the agent also checks.

#### What leaves your machine

Only two things: the search itself, which goes to Envato's MCP server, and the download of each
preview image from Envato's image CDN so it can be embedded in the page. The gallery server
sends nothing anywhere.

### If the skill does not start on its own

Whether an agent picks a skill up from a plain request depends on what its skill list shows, and
some setups drop the descriptions from that list when there are many skills installed. An agent
may then call the Envato search tool directly and give you a text list instead of the gallery.
Two ways to make it certain:

- Run the command, which always uses the skill:

  ```text
  /envato-search-gallery:envato-search 10 landscape photos of a compounding pharmacy
  ```

- Or name the skill in your request: "Use the envato-search-gallery skill to find ...".

The plugin's commands are namespaced by plugin name, so the command above is the form that has
been tested. Some setups also accept the short `/envato-search`; try it and see.

## Themes

The page look is not written into the script. It is read from a theme file, and the default is
[themes/jason-armstrong.json](skills/envato-search-gallery/themes/jason-armstrong.json): Jason Armstrong's
design system (JA). It is near-monochrome with a Forest green accent (coral is kept for errors and
warnings), Hanken Grotesk and IBM Plex Mono, light and dark. The file is a bundled copy of the master
theme, so the plugin works when installed alone.

```bash
python3 skills/envato-search-gallery/scripts/build_gallery.py results.json --theme jason-armstrong
python3 skills/envato-search-gallery/scripts/build_gallery.py results.json --theme path/to/my-theme.json
```

- `--theme NAME` loads `themes/NAME.json`; `--theme PATH` loads a theme file from anywhere. A
  missing or incomplete theme stops with a message that names what is missing.
- The fonts are embedded in each page as base64 (about 180 KB), so a page needs no network and
  looks the same offline. The latin and latin-extended subsets are included (Western and Central
  European); other scripts, such as Thai, fall back to the system font.
- The fonts are under the SIL Open Font Licence. Their licence texts are in
  [fonts/](skills/envato-search-gallery/fonts/).
- A theme can carry a brand logo (`brand` in the theme file: a path to an SVG or PNG, its height,
  above the title or top left, and an optional dark-mode version). The bundled theme sets the JA
  mark, which shows above the title.
- A theme must have `schema_version` 2. Any other version stops with a message.
- The master theme is designed and changed with the
  [design-system-creator](https://github.com/jason-armstrong-72/design-system-creator) plugin.
  Check that the bundled copy is up to date with `python3 skills/envato-search-gallery/scripts/check_theme_sync.py`;
  refresh it with `--update`. [themes/README.md](themes/README.md) has the details.
- The look before the JA theme is kept at the git tag `classic-look`
  (`git show classic-look:skills/envato-search-gallery/scripts/build_gallery.py`).

## Layout

```text
commands/envato-search.md      the /envato-search-gallery:envato-search command
skills/envato-search-gallery/
  SKILL.md                     what the agent does, step by step
  scripts/build_gallery.py     results JSON in, self-contained HTML out (stdlib only)
  scripts/gallery_server.py    shared local server for the pages, exits when idle
  scripts/check_theme_sync.py  checks the bundled theme against the master, and refreshes it
  themes/jason-armstrong.json  the default look: colour, type, spacing, shape, fonts
  themes/assets/               the JA mark (light and dark)
  fonts/                       the theme's font files (woff2) and their licences
  references/filters.json      filters per asset type, from the MCP tool schemas
  references/example-input.json
themes/                        theme README: where the look comes from and how to refresh the copy
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
