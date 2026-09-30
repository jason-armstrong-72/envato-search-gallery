#!/usr/bin/env python3
"""Build a self-contained HTML gallery from Envato MCP search results.

Usage:
    build_gallery.py results.json [--out PATH] [--open] [--no-serve]
    build_gallery.py - < results.json

By default the page is written to ~/.cache/envato-gallery and served by a small local server
(gallery_server.py), and the `open:` line holds an http://localhost link. If the server cannot
start, or --no-serve or --out is used, the `open:` line holds a file:// link instead. Nothing
opens in a browser unless --open is given.

Input JSON:
    {
      "query": "compounding pharmacy",
      "asset_type": "photos",              # key in references/filters.json
      "sort": "popular",
      "filters": {"orientation": "landscape"},   # filters actually applied, may be {}
      "results": [
        {"title": "...", "author": "...", "link": "https://elements.envato.com/...",
         "img": "https://elements-resized.envatousercontent.com/...&s=<signature>"}
      ]
    }

Each `img` must be the FULL signed URL from the search result, including the trailing
`&s=` signature. A truncated URL makes the CDN answer "Wrong signature". Previews are
downloaded here and embedded as base64, so the output file opens offline and needs no
network, account or server.

Standard library only.
"""
import argparse
import base64
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import gallery_server

KEEP_DAYS = 7
FILTERS_PATH = Path(__file__).resolve().parent.parent / "references" / "filters.json"
USER_AGENT = "Mozilla/5.0 (envato-search-gallery)"


def fetch_preview(item):
    """Download one preview and return it as a data URI, or raise with a clear reason."""
    url = item.get("img", "")
    if not url:
        raise ValueError("no img url")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            ctype = resp.headers.get_content_type()
    except urllib.error.HTTPError as err:
        # the CDN answers a bad or truncated signature with a 4xx and a short text body
        ctype, body = "error", err.read()
    if not ctype.startswith("image/"):
        hint = body[:60].decode("utf-8", "replace")
        raise ValueError(
            f"not an image (got {ctype}: {hint!r}). "
            "If this says 'Wrong signature', the img URL was truncated: copy it whole, "
            "including the trailing &s=... token."
        )
    return f"data:{ctype};base64,{base64.b64encode(body).decode('ascii')}"


def load_filters(asset_type):
    try:
        data = json.loads(FILTERS_PATH.read_text())
    except (OSError, ValueError):
        return {}
    return data.get(asset_type, {})


def filters_panel(asset_type, applied):
    available = load_filters(asset_type)
    if not available:
        return ""
    rows = []
    for name, values in available.items():
        is_applied = name in applied
        if isinstance(values, list):
            chips = "".join(
                '<span class="chip{}">{}</span>'.format(
                    " on" if is_applied and str(applied[name]) == v else "", html.escape(v)
                )
                for v in values
            )
            body = f'<div class="chips">{chips}</div>'
        else:
            body = f'<div class="note">{html.escape(str(values))}</div>'
        mark = " &middot; applied" if is_applied else ""
        rows.append(
            f'<details{" open" if is_applied else ""}><summary>{html.escape(name)}{mark}</summary>{body}</details>'
        )
    return (
        '<section class="filters"><h2>Filters available for {}</h2>{}</section>'.format(
            html.escape(asset_type), "".join(rows)
        )
    )


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Envato results: __TITLE__</title>
<style>
  :root {
    --bg: #faf9f7; --surface: #ffffff; --border: #e4e1da; --ink: #1f1d1a; --ink-soft: #6b6559;
    --accent: #0f6e5c; --accent-soft: #e4f2ee; --chip-bg: #f0ede6; --chip-ink: #57524a;
    --scrim: rgba(20, 18, 15, 0.86);
    --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    --mono: ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #171613; --surface: #201f1b; --border: #34322c; --ink: #f1efe9; --ink-soft: #a39c8d;
      --accent: #4fd6b6; --accent-soft: #1c332d; --chip-bg: #2a2823; --chip-ink: #c9c3b6;
      color-scheme: dark;
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink); font-family: var(--font);
         padding: 32px 20px 48px; max-width: 1120px; margin-inline: auto; }
  header { display: flex; flex-direction: column; gap: 6px; margin-bottom: 24px; }
  .eyebrow { font: 500 12px var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--accent); }
  h1 { margin: 0; font-size: clamp(26px, 4vw, 38px); font-weight: 650; text-wrap: balance; }
  .meta { color: var(--ink-soft); font-size: 14px; display: flex; flex-wrap: wrap; gap: 4px 14px; }
  .meta strong { color: var(--ink); font-weight: 600; }
  .filters { background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
             padding: 12px 16px; margin-bottom: 24px; display: flex; flex-wrap: wrap; gap: 4px 20px; }
  .filters h2 { flex-basis: 100%; margin: 0 0 4px; font: 600 12px var(--mono); text-transform: uppercase;
                letter-spacing: .06em; color: var(--ink-soft); }
  details { min-width: 0; }
  summary { cursor: pointer; font-size: 13px; padding: 4px 0; color: var(--ink); }
  details[open] { flex-basis: 100%; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; padding: 4px 0 10px; }
  .chip { font-size: 12px; padding: 3px 9px; border-radius: 999px; background: var(--chip-bg); color: var(--chip-ink); }
  .chip.on { background: var(--accent-soft); color: var(--accent); font-weight: 600; }
  .note { font-size: 12px; color: var(--ink-soft); padding: 2px 0 10px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 18px; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; overflow: hidden;
          display: flex; flex-direction: column; min-width: 0; }
  .thumb { all: unset; display: block; cursor: zoom-in; position: relative; }
  .thumb:focus-visible { outline: 3px solid var(--accent); outline-offset: -3px; }
  .thumb img { width: 100%; aspect-ratio: 4 / 3; object-fit: cover; display: block; background: var(--chip-bg); }
  .card-body { padding: 12px 14px 14px; display: flex; flex-direction: column; gap: 6px; flex: 1; }
  .card-title { font-size: 14px; font-weight: 600; line-height: 1.35; overflow-wrap: anywhere; }
  .card-author { font-size: 12px; color: var(--ink-soft); }
  .card-link, .lb-link { margin-top: auto; font-size: 13px; font-weight: 600; color: var(--accent); text-decoration: none; }
  .card-link::after, .lb-link::after { content: " \2197"; }
  .lb { position: fixed; inset: 0; background: var(--scrim); display: none; align-items: center; justify-content: center;
        flex-direction: column; gap: 14px; padding: 24px 16px; z-index: 10; }
  .lb[data-open="true"] { display: flex; }
  .lb img { max-width: min(96vw, 1200px); max-height: 74vh; border-radius: 8px; background: var(--chip-bg); }
  .lb-cap { color: #f1efe9; text-align: center; max-width: 720px; display: flex; flex-direction: column; gap: 6px; align-items: center; }
  .lb-title { font-size: 15px; font-weight: 600; }
  .lb-author { font-size: 13px; color: #b9b2a3; }
  .lb-link { color: #4fd6b6; margin: 0; }
  .lb button { all: unset; cursor: pointer; color: #f1efe9; font-size: 28px; line-height: 1; padding: 10px 14px;
               border-radius: 8px; background: rgba(255,255,255,.1); position: absolute; }
  .lb button:hover, .lb button:focus-visible { background: rgba(255,255,255,.22); }
  .lb-close { top: 14px; right: 14px; }
  .lb-prev { left: 12px; top: 50%; transform: translateY(-50%); }
  .lb-next { right: 12px; top: 50%; transform: translateY(-50%); }
  footer { margin-top: 28px; padding-top: 14px; border-top: 1px solid var(--border); font-size: 12px; color: var(--ink-soft); }
  @media (prefers-reduced-motion: no-preference) { .lb[data-open="true"] { animation: fade .12s ease-out; } }
  @keyframes fade { from { opacity: 0; } }
</style>
</head>
<body>
<header>
  <div class="eyebrow">Envato Elements &middot; __ASSET_TYPE__</div>
  <h1>&ldquo;__QUERY__&rdquo;</h1>
  <div class="meta">
    <span><strong>__COUNT__</strong> results</span>
    <span>sorted by <strong>__SORT__</strong></span>
    <span>__APPLIED__</span>
  </div>
</header>
__FILTERS__
<div class="grid" id="grid"></div>
<footer>
  Watermarked previews for review only. Click an image to enlarge it, then use &ldquo;View on Envato&rdquo;
  to license and download the original on elements.envato.com. Unofficial tool; not affiliated with Envato.
</footer>

<div class="lb" id="lb" role="dialog" aria-modal="true" aria-label="Image preview" data-open="false">
  <button class="lb-close" id="lbClose" aria-label="Close">&times;</button>
  <button class="lb-prev" id="lbPrev" aria-label="Previous image">&lsaquo;</button>
  <img id="lbImg" alt="">
  <div class="lb-cap">
    <div class="lb-title" id="lbTitle"></div>
    <div class="lb-author" id="lbAuthor"></div>
    <a class="lb-link" id="lbLink" target="_blank" rel="noopener">View on Envato</a>
  </div>
  <button class="lb-next" id="lbNext" aria-label="Next image">&rsaquo;</button>
</div>

<script type="application/json" id="data">__DATA__</script>
<script>
  var items = JSON.parse(document.getElementById('data').textContent);
  var grid = document.getElementById('grid');
  var lb = document.getElementById('lb'), lbImg = document.getElementById('lbImg');
  var current = -1, opener = null;

  items.forEach(function (it, i) {
    var card = document.createElement('div'); card.className = 'card';
    var thumb = document.createElement('button'); thumb.className = 'thumb'; thumb.type = 'button';
    thumb.setAttribute('aria-label', 'Enlarge: ' + it.title);
    var img = document.createElement('img'); img.src = it.src; img.alt = it.title; img.loading = 'lazy';
    thumb.appendChild(img);
    thumb.addEventListener('click', function () { openAt(i, thumb); });
    var body = document.createElement('div'); body.className = 'card-body';
    var t = document.createElement('div'); t.className = 'card-title'; t.textContent = it.title;
    var a = document.createElement('div'); a.className = 'card-author'; a.textContent = it.author ? 'by ' + it.author : '';
    var l = document.createElement('a'); l.className = 'card-link'; l.href = it.link; l.target = '_blank';
    l.rel = 'noopener'; l.textContent = 'View on Envato';
    body.append(t, a, l); card.append(thumb, body); grid.appendChild(card);
  });

  function show(i) {
    current = (i + items.length) % items.length;
    var it = items[current];
    lbImg.src = it.src; lbImg.alt = it.title;
    document.getElementById('lbTitle').textContent = it.title;
    document.getElementById('lbAuthor').textContent = it.author ? 'by ' + it.author : '';
    document.getElementById('lbLink').href = it.link;
  }
  function openAt(i, from) { opener = from; show(i); lb.dataset.open = 'true'; document.getElementById('lbClose').focus(); }
  function closeLb() { lb.dataset.open = 'false'; if (opener) opener.focus(); }
  document.getElementById('lbClose').addEventListener('click', closeLb);
  document.getElementById('lbPrev').addEventListener('click', function () { show(current - 1); });
  document.getElementById('lbNext').addEventListener('click', function () { show(current + 1); });
  lb.addEventListener('click', function (e) { if (e.target === lb) closeLb(); });
  document.addEventListener('keydown', function (e) {
    if (lb.dataset.open !== 'true') return;
    if (e.key === 'Escape') closeLb();
    else if (e.key === 'ArrowLeft') show(current - 1);
    else if (e.key === 'ArrowRight') show(current + 1);
  });
</script>
</body>
</html>
"""


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or "results"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="results JSON file, or - for stdin")
    ap.add_argument("--out", help="output HTML path (default: the gallery cache folder, served locally)")
    ap.add_argument("--open", action="store_true", help="also open the page in the default browser")
    ap.add_argument("--no-serve", action="store_true", help="do not start the local server; print a file:// link")
    ap.add_argument("--no-open", action="store_true", help=argparse.SUPPRESS)  # old flag, now the default
    args = ap.parse_args()

    raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text()
    spec = json.loads(raw)
    results = spec.get("results") or []
    if not results:
        sys.exit("error: no results in input")

    def safe_fetch(item):
        try:
            return fetch_preview(item), None
        except Exception as exc:  # report every failure, not just the first
            return None, str(exc)

    with ThreadPoolExecutor(max_workers=8) as pool:
        fetched = list(pool.map(safe_fetch, results))

    items, failures = [], []
    for item, (src, err) in zip(results, fetched):
        if err:
            failures.append(f"  - {item.get('title', '?')[:60]}: {err}")
            continue
        items.append({
            "title": item.get("title", ""),
            "author": item.get("author", ""),
            "link": item.get("link", "#"),
            "src": src,
        })
    if not items:
        sys.exit("error: no previews could be downloaded\n" + "\n".join(failures))

    asset_type = spec.get("asset_type", "photos")
    applied = spec.get("filters") or {}
    applied_text = (
        "filters: " + ", ".join(f"{k} = {v}" for k, v in applied.items()) if applied else "no filters applied"
    )
    # "</" inside inline JSON would end the script tag early
    data_json = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")

    page = (
        TEMPLATE.replace("__TITLE__", html.escape(spec.get("query", "search")))
        .replace("__QUERY__", html.escape(spec.get("query", "search")))
        .replace("__ASSET_TYPE__", html.escape(asset_type))
        .replace("__COUNT__", str(len(items)))
        .replace("__SORT__", html.escape(spec.get("sort", "popular")))
        .replace("__APPLIED__", html.escape(applied_text))
        .replace("__FILTERS__", filters_panel(asset_type, applied))
        .replace("__DATA__", data_json)
    )

    cache = gallery_server.DEFAULT_DIR
    out = Path(args.out) if args.out else cache / f"{slug(spec.get('query', 'results'))}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    if not args.out:
        prune(cache)

    print(f"wrote {out} ({out.stat().st_size // 1024} KB, {len(items)} images)")
    link = out.resolve().as_uri()
    if not args.no_serve and out.resolve().parent == cache.resolve():
        try:
            port = gallery_server.ensure(cache, gallery_server.DEFAULT_IDLE)
        except Exception as exc:
            port = None
            print(f"note: local server failed ({exc})")
        if port:
            link = f"http://localhost:{port}/{out.name}"
        else:
            print("note: local server unavailable; using a file:// link, which may need copying into a browser")
    print(f"open: {link}")
    if failures:
        print(f"{len(failures)} preview(s) skipped:\n" + "\n".join(failures))
    if args.open:
        webbrowser.open(link)


def prune(folder):
    """Delete gallery pages older than KEEP_DAYS so the cache folder does not grow."""
    cutoff = time.time() - KEEP_DAYS * 86400
    for page in folder.glob("*.html"):
        try:
            if page.stat().st_mtime < cutoff:
                page.unlink()
        except OSError:
            pass

if __name__ == "__main__":
    main()
