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
downloaded here and embedded as base64, so the page needs no server once it is built. An `img` that is a
local path (relative to the input file) or a file:// URL is read from disk instead, which is how
references/offline-input.json builds with no network.

The look is the JA design system and nothing else: the page inlines the skill's tokens.css and
components.css and is written in its components (ds-page, ds-media-grid, ds-lightbox and so on). The
skill is read from $JA_SKILL if that is set, else ~/.claude/skills/jason-armstrong-design-system. If that
folder or either CSS file is missing, the bundled copy in themes/ja/ is used instead (see
check_theme_sync.py), and the build prints one line saying which. The two Google Fonts links, the brand
logo, its alt text, height and placement come from the same folder's theme.json. The page follows the
display's light or dark setting and has a Light, Dark and System switch.

Standard library only.
"""
import argparse
import base64
import html
import json
import re
import sys
import urllib.error
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import check_theme_sync
import gallery_server

KEEP_DAYS = 7
SKILL_DIR = Path(__file__).resolve().parent.parent
FILTERS_PATH = SKILL_DIR / "references" / "filters.json"
BUNDLED_DIR = check_theme_sync.BUNDLED
USER_AGENT = "Mozilla/5.0 (envato-search-gallery)"
MIME = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp"}


def read_local_image(url, base):
    """Read an image from disk and return it as a data URI. A relative path is taken from `base`."""
    path = Path(url[len("file://"):] if url.startswith("file://") else url)
    path = path if path.is_absolute() else Path(base) / path
    mime = MIME.get(path.suffix.lower())
    if not mime:
        raise ValueError(f"unsupported image type {path.suffix or '(none)'}: {path}")
    try:
        return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
    except OSError as exc:
        raise ValueError(f"image file not readable: {exc}")


def fetch_preview(item, base="."):
    """Download one preview and return it as a data URI, or raise with a clear reason.

    An `img` that is not an http(s) URL is read from disk (a relative path from `base`), which lets
    references/offline-input.json build without a network.
    """
    url = item.get("img", "")
    if not url:
        raise ValueError("no img url")
    if not url.startswith(("http://", "https://")):
        return read_local_image(url, base)
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
    """The filters available for the asset type, as a ds-card holding a ds-accordion of details."""
    available = load_filters(asset_type)
    if not available:
        return ""
    rows = []
    for name, values in available.items():
        is_applied = name in applied
        if isinstance(values, list):
            chips = "".join(
                '<span class="ds-chip{}">{}</span>'.format(
                    " is-selected" if is_applied and str(applied[name]) == v else "", html.escape(v)
                )
                for v in values
            )
            body = f'<div class="ds-row">{chips}</div>'
        else:
            body = f'<p class="ds-help">{html.escape(str(values))}</p>'
        mark = " &middot; applied" if is_applied else ""
        rows.append(
            f'<details{" open" if is_applied else ""}><summary>{html.escape(name)}{mark}</summary>{body}</details>'
        )
    return (
        '<section class="ds-section"><div class="ds-card"><h2>Filters available for {}</h2>'
        '<div class="ds-accordion">{}</div></div></section>'.format(html.escape(asset_type), "".join(rows))
    )


# ---- the JA design system ---------------------------------------------------------------------

def resolve_source():
    """Pick where the design system is read from. Returns (folder, one line saying which).

    The live skill ($JA_SKILL, else ~/.claude/skills/jason-armstrong-design-system) is used when both
    tokens.css and components.css are there. Otherwise the bundled copy in themes/ja/ is.
    """
    live = check_theme_sync.live_dir()
    if check_theme_sync.live_usable(live):
        ver = check_theme_sync.version_of(live)
        return live, f"theme: JA skill at {live}" + (f" ({ver})" if ver else "")
    if not check_theme_sync.live_usable(BUNDLED_DIR):
        sys.exit(f"error: no tokens.css and components.css in the JA skill ({live}) or the bundled copy ({BUNDLED_DIR})")
    ver = check_theme_sync.version_of(BUNDLED_DIR)
    return BUNDLED_DIR, (f"theme: bundled copy in themes/ja" + (f" ({ver})" if ver else "")
                         + f", because the JA skill is not usable at {live}")


def read_theme_json(source):
    """theme.json from the source folder, else from the bundled copy, else {}. Read for fonts and brand only."""
    for folder in (source, BUNDLED_DIR):
        try:
            return json.loads((Path(folder) / "theme.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return {}


def font_links(theme):
    """The two Google Fonts <link> tags, from theme.json fonts.*.css_url, as the JA recipe has them."""
    urls = [(theme.get("fonts") or {}).get(k, {}).get("css_url") for k in ("sans", "mono")]
    return "\n".join(f'<link rel="stylesheet" href="{html.escape(u, quote=True)}">' for u in urls if u)


def logo_uri(rel, source):
    """A logo file as a data URI, from the source folder, else the bundled copy. None when not found."""
    if not rel:
        return None
    mime = MIME.get(Path(rel).suffix.lower())
    if not mime:
        return None
    for folder in (source, BUNDLED_DIR):
        try:
            return f"data:{mime};base64,{base64.b64encode((Path(folder) / rel).read_bytes()).decode('ascii')}"
        except OSError:
            continue
    return None


def brand_parts(theme, source):
    """The brand mark as (html, placement), or ("", "above") when there is none.

    Markup is the recipe's ds-brand with a light and a dark image; alt text, height and placement
    ("above" or "topleft") come from theme.json brand.
    """
    brand = theme.get("brand") or {}
    light = logo_uri(brand.get("logo"), source)
    if not light:
        return "", "above"
    dark = logo_uri(brand.get("logo_dark"), source)
    alt = html.escape(brand.get("alt", ""), quote=True)
    height = int(brand.get("height_px", 28))
    imgs = f'<img class="ds-brand-light" src="{light}" alt="{alt}" height="{height}">'
    if dark:
        imgs += f'<img class="ds-brand-dark" src="{dark}" alt="{alt}" height="{height}">'
    place = brand.get("placement", "above")
    return f'<span class="ds-brand">{imgs}</span>', place if place in ("above", "topleft") else "above"


# The recipe's body rules, then two rules JA cannot express: it has no muted-text class, so the
# header line and the footer take --muted this way, and the <strong> counts go back to ink.
PAGE_CSS = """body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: var(--t-body-f);
  font-size: var(--t-body-s);
  font-weight: var(--t-body-w);
  line-height: var(--t-body-lh);
}
h1, h2, h3, h4, p { margin: 0; }
.t-display, .ds-prose h1 { overflow-wrap: anywhere; }
/* JA has no muted-text class: the results line and the footer use the muted token */
.gallery-muted { color: var(--muted); }
.gallery-muted strong { color: var(--ink); font-weight: inherit; }
"""

# A section's content starts at the page padding: nothing here sets a width, gap or size.
TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Envato results: __TITLE__</title>
__FONT_LINKS__
<style>__CSS__</style>
</head>
<body>
<main class="ds-page ds-stack is-loose">
  <header class="ds-row is-between">
    __BRAND_TOPLEFT__<div class="ds-theme-switch" role="group" aria-label="Colour mode">
      <button type="button" data-mode="light" aria-pressed="false" aria-label="Light" title="Light"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="3"/><path d="M8 1v1.5M8 13.5V15M1 8h1.5M13.5 8H15M3.05 3.05l1.05 1.05M11.9 11.9l1.05 1.05M12.95 3.05L11.9 4.1M4.1 11.9l-1.05 1.05"/></svg></button>
      <button type="button" data-mode="dark" aria-pressed="false" aria-label="Dark" title="Dark"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M13.5 9.5A5.5 5.5 0 0 1 6.5 2.5a5.5 5.5 0 1 0 7 7z"/></svg></button>
      <button type="button" data-mode="system" aria-pressed="true" aria-label="System" title="System"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="1.75" y="2.5" width="12.5" height="8.5" rx="1"/><path d="M8 11v2.5M5 13.5h6"/></svg></button>
    </div>
  </header>
  <section class="ds-section ds-stack is-loose">
    __BRAND_ABOVE__<div class="ds-stack is-tight">
      <p class="t-eyebrow">Envato Elements &middot; __ASSET_TYPE__</p>
      <h1 class="t-display">&ldquo;__QUERY__&rdquo;</h1>
      <div class="ds-row t-label gallery-muted">
        <span><strong>__COUNT__</strong> results</span>
        <span>sorted by <strong>__SORT__</strong></span>
        <span>__APPLIED__</span>
      </div>
    </div>
  </section>
  __FILTERS__
  <section class="ds-section">
    <div class="ds-media-grid" id="grid"></div>
  </section>
  <footer class="ds-section">
    <p class="t-caption gallery-muted">Watermarked previews for review only. Click an image to enlarge it, then use &ldquo;View on Envato&rdquo;
    to license and download the original on elements.envato.com. Unofficial tool; not affiliated with Envato.</p>
  </footer>
</main>

<div class="ds-lightbox" id="lb" role="dialog" aria-modal="true" aria-label="Image preview">
  <button type="button" class="ds-icon-btn ds-lightbox-close" id="lbClose" aria-label="Close"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg></button>
  <button type="button" class="ds-icon-btn ds-lightbox-prev" id="lbPrev" aria-label="Previous image"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 3.5L5.5 8l4.5 4.5"/></svg></button>
  <figure class="ds-lightbox-figure">
    <img id="lbImg" alt="">
    <figcaption>
      <p class="ds-media-title" id="lbTitle"></p>
      <p class="ds-media-meta" id="lbAuthor"></p>
      <a class="ds-btn" id="lbLink" target="_blank" rel="noopener">View on Envato</a>
    </figcaption>
  </figure>
  <button type="button" class="ds-icon-btn ds-lightbox-next" id="lbNext" aria-label="Next image"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 3.5L10.5 8 6 12.5"/></svg></button>
</div>

<script type="application/json" id="data">__DATA__</script>
<script>
  (function () {
    var root = document.documentElement;
    var buttons = document.querySelectorAll(".ds-theme-switch button");
    function apply(mode) {
      if (mode === "light" || mode === "dark") {
        root.setAttribute("data-theme", mode);
      } else {
        root.removeAttribute("data-theme");
      }
      Array.prototype.forEach.call(buttons, function (b) {
        b.setAttribute("aria-pressed", String(b.getAttribute("data-mode") === mode));
      });
    }
    var saved = "system";
    try { saved = localStorage.getItem("theme") || "system"; } catch (e) {}
    apply(saved);
    Array.prototype.forEach.call(buttons, function (b) {
      b.addEventListener("click", function () {
        var mode = b.getAttribute("data-mode");
        apply(mode);
        try { localStorage.setItem("theme", mode); } catch (e) {}
      });
    });
  })();
</script>
<script>
  var items = JSON.parse(document.getElementById('data').textContent);
  var grid = document.getElementById('grid');
  var lb = document.getElementById('lb'), lbImg = document.getElementById('lbImg');
  var current = -1, opener = null;

  items.forEach(function (it, i) {
    var card = document.createElement('figure'); card.className = 'ds-media-card';
    var thumb = document.createElement('button'); thumb.className = 'ds-media-thumb'; thumb.type = 'button';
    thumb.setAttribute('aria-label', 'Enlarge: ' + it.title);
    var img = document.createElement('img'); img.src = it.src; img.alt = it.title; img.loading = 'lazy';
    thumb.appendChild(img);
    thumb.addEventListener('click', function () { openAt(i, thumb); });
    var cap = document.createElement('figcaption');
    var t = document.createElement('p'); t.className = 'ds-media-title'; t.textContent = it.title;
    cap.appendChild(t);
    if (it.author) {
      var a = document.createElement('p'); a.className = 'ds-media-meta'; a.textContent = 'By ' + it.author;
      cap.appendChild(a);
    }
    var row = document.createElement('div'); row.className = 'ds-row';
    var l = document.createElement('a'); l.className = 'ds-btn'; l.href = it.link; l.target = '_blank';
    l.rel = 'noopener'; l.textContent = 'View on Envato';
    row.appendChild(l); cap.appendChild(row);
    card.append(thumb, cap); grid.appendChild(card);
  });

  function show(i) {
    current = (i + items.length) % items.length;
    var it = items[current];
    lbImg.src = it.src; lbImg.alt = it.title;
    document.getElementById('lbTitle').textContent = it.title;
    var author = document.getElementById('lbAuthor');
    author.textContent = it.author ? 'By ' + it.author : '';
    author.hidden = !it.author;
    document.getElementById('lbLink').href = it.link;
  }
  function isOpen() { return lb.classList.contains('is-open'); }
  function openAt(i, from) { opener = from; show(i); lb.classList.add('is-open'); document.getElementById('lbClose').focus(); }
  function closeLb() { lb.classList.remove('is-open'); if (opener) opener.focus(); }
  document.getElementById('lbClose').addEventListener('click', closeLb);
  document.getElementById('lbPrev').addEventListener('click', function () { show(current - 1); });
  document.getElementById('lbNext').addEventListener('click', function () { show(current + 1); });
  lb.addEventListener('click', function (e) { if (e.target === lb) closeLb(); });
  document.addEventListener('keydown', function (e) {
    if (!isOpen()) return;
    if (e.key === 'Escape') closeLb();
    else if (e.key === 'ArrowLeft') show(current - 1);
    else if (e.key === 'ArrowRight') show(current + 1);
  });
</script>
<script>
  (function () {
    var FLOOR = 24;
    var titles = document.querySelectorAll(".t-display, .ds-prose h1");
    function fit() {
      Array.prototype.forEach.call(titles, function (h) {
        h.style.fontSize = "";
        h.style.overflowWrap = "normal";
        var size = parseFloat(getComputedStyle(h).fontSize);
        while (h.scrollWidth > h.clientWidth + 0.5 && size > FLOOR) {
          size -= 1;
          h.style.fontSize = size + "px";
        }
        h.style.overflowWrap = "";
      });
    }
    fit();
    if (document.fonts && document.fonts.ready) { document.fonts.ready.then(fit); }
    window.addEventListener("resize", fit);
  })();
</script>
</body>
</html>
"""


def fill(template, values):
    """Replace each __NAME__ once, in one pass, so inserted text is never scanned for more names."""
    return re.sub(r"__([A-Z_]+)__", lambda m: values.get(m.group(1), m.group(0)), template)


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

    source, source_line = resolve_source()
    print(source_line)
    if source == BUNDLED_DIR:
        # the live skill is not usable, but a partly present one can still be compared
        note = check_theme_sync.behind_note()
        if note:
            print(f"warning: {note}", file=sys.stderr)
    raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text()
    spec = json.loads(raw)
    input_base = Path.cwd() if args.input == "-" else Path(args.input).resolve().parent
    results = spec.get("results") or []
    if not results:
        sys.exit("error: no results in input")

    def safe_fetch(item):
        try:
            return fetch_preview(item, input_base), None
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

    theme = read_theme_json(source)
    brand_html, place = brand_parts(theme, source)
    tokens = (source / "tokens.css").read_text(encoding="utf-8")
    components = (source / "components.css").read_text(encoding="utf-8")
    query = html.escape(spec.get("query", "search"))
    page = fill(TEMPLATE, {
        "TITLE": query,
        "FONT_LINKS": font_links(theme),
        "CSS": "\n" + tokens + "\n" + components + "\n" + PAGE_CSS,
        "BRAND_TOPLEFT": brand_html if place == "topleft" else "",
        "BRAND_ABOVE": brand_html if place == "above" else "",
        "QUERY": query,
        "ASSET_TYPE": html.escape(asset_type),
        "COUNT": str(len(items)),
        "SORT": html.escape(spec.get("sort", "popular")),
        "APPLIED": html.escape(applied_text),
        "FILTERS": filters_panel(asset_type, applied),
        "DATA": data_json,
    })

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
    """Delete gallery pages older than KEEP_DAYS so the cache folder does not grow.

    One rule, kept in gallery_server.prune(): only pages this builder made are removed, so other
    files served from the same folder (option pages, for instance) are left alone.
    """
    return gallery_server.prune(folder)


if __name__ == "__main__":
    main()
