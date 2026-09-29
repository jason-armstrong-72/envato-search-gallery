---
name: envato-search-gallery
description: Search Envato Elements through the Envato MCP server and show the results as a quick visual gallery, so the user can scan images and pick one instead of opening links one at a time. Use when the user asks to find, source, browse or preview stock photos, graphics, illustrations, video thumbnails or other visual assets from Envato Elements, or says "search Envato for ...". Needs the Envato MCP server (https://mcp.envato.com/mcp) connected. Search only, it never downloads or licenses anything.
---

# Envato search gallery

The Envato MCP server is **search only**. It returns titles, item links and watermarked
previews, and cannot download or license anything. This skill fills the gap between a
raw list of links and a full search on elements.envato.com: run the search, show the
previews in one page, let the user pick, hand back the Envato link.

## Steps

1. **Choose the search tool** for the asset type: `search_photos`, `search_graphics`,
   `search_stock_video`, `search_fonts` and so on (`search_` plus the type, hyphens to
   underscores). Avoid `search_items`, which is deprecated.
2. **Tell the user the filters available for that type before searching**, one line, only
   the ones likely to matter (photos: orientation, number_of_people, colors). The full
   list is in `references/filters.json`. If the request already implies a filter ("portrait
   photos"), apply it and say so.
3. **Search.** Set `perPage` to the number of images asked for. Default 10, maximum 20
   per call; for more, request further `page`s and merge. Default `sortBy` is `popular`;
   use `relevance` when the user described something specific.
4. **Write the results to a JSON file** in a temp directory (see `references/example-input.json`).
   From each card in the tool result take the image `src` as `img`, the image `alt` as
   `title`, the "by ..." text as `author`, and the link button's `url` as `link`.
   **Copy every `img` URL whole, including the trailing `&s=<signature>`.** The CDN
   rejects a truncated URL with "Wrong signature", and the script will say so.
5. **Build the gallery:**

   ```bash
   python3 scripts/build_gallery.py /tmp/envato-results.json
   ```

   The path is relative to this skill's folder. The script downloads the previews,
   embeds them in one self-contained HTML file, and opens it in the default browser
   (add `--no-open` to only write it, `--out PATH` to choose where). Standard library
   only, no install step.
6. **Report** the file path and the count. Skipped previews are listed by the script;
   mention them.
7. **When the user picks**, give the Envato item link(s) as clickable URLs. Licensing and
   download happen on elements.envato.com, and that needs an active Elements subscription.
   Do not try to fetch the full-size image.

## Gallery behaviour

Click a thumbnail to enlarge it (arrow keys move between images, Escape closes). The
enlarged view is still the 600px watermarked preview, because the signed URL fixes the
size, so it is good for judging composition, not detail. Applied and available filters
are shown as chips. The page is static: to refine a search, ask the agent, which re-runs
the search and rebuilds the page.

## Notes

- Anonymous use works: no OAuth, and searching needs no subscription. Only licensing and
  downloading do.
- If the client already renders the MCP result as an image grid inline (Claude Desktop may
  do this), the gallery page is unnecessary. Say so and skip it.
- Only visual types have image previews. For music and sound effects, report titles and
  links as text instead.
- Previews are for review only. Do not commit or redistribute them.
- `references/filters.json` was written from the tool schemas on 2026-09-30. If a call is
  rejected for an unknown filter or value, the schema has changed: read the live tool
  definition and update the file.
