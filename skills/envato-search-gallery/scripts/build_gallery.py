#!/usr/bin/env python3
"""Build a self-contained HTML gallery from Envato MCP search results.

Usage:
    build_gallery.py results.json [--out PATH] [--theme NAME|PATH] [--open] [--no-serve]
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

The look comes from a theme file (default: themes/jason-armstrong.json next to this script's
folder, a bundled copy of Jason Armstrong's master theme, schema version 2). Colours, type,
spacing, shape and fonts are all read from it, and the fonts are embedded as base64, so a theme
needs no network either. When the default theme is used and the master theme is found on this
machine, a one-line warning is printed if the bundled copy is behind it
(see check_theme_sync.py). Pass --theme NAME for another file in themes/, or
--theme PATH for a theme file anywhere. The page follows the display's light or dark setting and
has a Light, Dark and System switch.

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
SKILL_DIR = Path(__file__).resolve().parent.parent
FILTERS_PATH = SKILL_DIR / "references" / "filters.json"
THEMES_DIR = SKILL_DIR / "themes"
DEFAULT_THEME = "jason-armstrong"
SCHEMA_VERSION = 2
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



# ---- theme ------------------------------------------------------------------------------------

REQUIRED_ROLES = ["display", "title", "eyebrow", "meta", "author", "label", "option", "button"]
REQUIRED_COLOURS = ["bg", "surface", "border", "ink", "muted", "accent", "accent-text", "error", "warning",
                    "btn-bg", "btn-ink", "btn-arrow", "focus"]
REQUIRED_SPACING = ["pagex", "pagetop", "pagebot", "maxw", "hgap", "hmb", "fpadx", "fpady", "fgapy",
                    "fgapx", "fmb", "chipgap", "chipx", "chipy", "gridgap", "cardmin", "cpadt", "cpadx",
                    "cpadb", "cgap", "btnx", "btny", "btngap", "footmt", "footpt", "rcard", "rchip", "rbtn"]


def available_themes():
    return sorted(p.stem for p in THEMES_DIR.glob("*.json"))


def load_theme(name):
    """Load a theme by name (a file in themes/) or by path, and check it has what the page needs."""
    path = Path(name)
    if not (path.suffix == ".json" or "/" in name or "\\" in name):
        path = THEMES_DIR / f"{name}.json"
    try:
        theme = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        sys.exit(f"error: theme not found: {path}\navailable themes: {', '.join(available_themes()) or 'none'}")
    except ValueError as exc:
        sys.exit(f"error: theme {path} is not valid JSON: {exc}")
    if theme.get("schema_version") != SCHEMA_VERSION:
        sys.exit(
            f"error: theme {path.name} has schema_version {theme.get('schema_version')!r}; "
            f"this builder reads schema_version {SCHEMA_VERSION}"
        )
    missing = (
        [f"type.{r}" for r in REQUIRED_ROLES if r not in theme.get("type", {})]
        + [f"colour.{c}" for c in REQUIRED_COLOURS if c not in theme.get("colour", {})]
        + [f"spacing_and_shape.{k}" for k in REQUIRED_SPACING if k not in theme.get("spacing_and_shape", {})]
        + [k for k in ("sans", "mono") if k not in theme.get("fonts", {})]
    )
    if missing:
        sys.exit(f"error: theme {path.name} is missing: {', '.join(missing)}")
    return theme


def font_faces(theme, base):
    """@font-face rules with each listed file embedded as base64. A missing file is skipped."""
    faces, notes = [], []
    for entry in theme["fonts"].get("embed", []):
        file = Path(base) / entry["file"]
        try:
            data = base64.b64encode(file.read_bytes()).decode("ascii")
        except OSError:
            notes.append(f"font file not found, using the fallback font: {file}")
            continue
        rng = f'unicode-range:{entry["unicode_range"]};' if entry.get("unicode_range") else ""
        faces.append(
            '@font-face{font-family:"%s";font-style:normal;font-weight:%s;font-display:swap;%s'
            'src:url(data:font/woff2;base64,%s) format("woff2")}' % (entry["family"], entry["weight"], rng, data)
        )
    return "\n".join(faces), notes


def theme_vars(theme):
    """CSS custom properties for type, spacing, shape and both colour modes."""
    fonts = theme["fonts"]
    lines = [
        ':root{--font:"%s",%s;--mono:"%s",%s;'
        % (fonts["sans"]["family"], fonts["sans"].get("fallback", "sans-serif"),
           fonts["mono"]["family"], fonts["mono"].get("fallback", "monospace"))
    ]
    for role, v in theme["type"].items():
        lines.append(
            f'--t-{role}-s:{v["size_px"]}px;--t-{role}-w:{v["weight"]};'
            f'--t-{role}-tr:{v["tracking_em"]}em;--t-{role}-lh:{v["line_height"]};'
        )
    for key, v in theme["spacing_and_shape"].items():
        lines.append(f"--sp-{key}:{v['px']}px;")
    # the lightbox is dark in both modes, so its link uses the accent as it is in dark mode
    lines.append(f"--accent-on-dark:{theme['colour']['accent']['dark']};")
    lines.append(f"--ink-on-dark:{theme['colour']['ink']['dark']};--muted-on-dark:{theme['colour']['muted']['dark']};")
    lines.append("}")

    def colours(mode):
        c = theme["colour"]
        g = lambda k: c[k][mode]
        # the lightbox has no panel and shows captions straight on the backdrop, so it uses the theme's
        # dark (light-mode) backdrop in both modes: the light-tinted dark-mode one leaves the page readable behind
        backdrop = theme.get("components", {}).get("modal", {}).get("backdrop", {}).get("light", "rgba(0,0,0,.92)")
        return (
            f"--bg:{g('bg')};--surface:{g('surface')};--border:{g('border')};--ink:{g('ink')};"
            f"--muted:{g('muted')};--accent:{g('accent')};--accent-text:{g('accent-text')};"
            f"--error:{g('error')};--warning:{g('warning')};"
            f"--btn-bg:{g('btn-bg')};--btn-ink:{g('btn-ink')};--btn-arrow:{g('btn-arrow')};"
            f"--focus:{g('focus')};--lb-bg:{backdrop};color-scheme:{mode};"
        )

    light, dark = colours("light"), colours("dark")
    lines.append(f':root,:root[data-theme="light"]{{{light}}}')
    lines.append(f':root[data-theme="dark"]{{{dark}}}')
    # without JavaScript the page still follows the display setting
    lines.append(f"@media (prefers-color-scheme:dark){{:root:not([data-theme]){{{dark}}}}}")
    small = small_screen_sizes(theme)
    if small:
        rules = "".join(f"--t-{role}-s:{px}px;" for role, px in small.items())
        # a phone held sideways is wider than max_width_px, so a short touch screen counts as small too
        width = theme["small_screen"]["max_width_px"]
        lines.append(
            f"@media (max-width:{width}px),(pointer:coarse) and (max-height:{width}px){{:root{{{rules}}}}}"
        )
    return "\n".join(lines)


def small_screen_sizes(theme):
    """Type sizes that change on a narrow screen: small ones grow, the largest come down to a cap.

    The same two rules as the design-system-creator (its spec, section 3.8). A role listed under
    small_screen.roles is set outright. Returns {role: px} for the roles that change.
    """
    ss = theme.get("small_screen")
    if not ss:
        return {}
    out = {}
    for role, spec in theme["type"].items():
        size = spec["size_px"]
        if size < ss["grow_below_px"]:
            new = size + ss["grow_by_px"]
        elif size > ss["cap_px"]:
            new = ss["cap_px"]
        else:
            new = size
        new = ss.get("roles", {}).get(role, {}).get("size_px", new)
        if new != size:
            out[role] = new
    return out


def expand_roles(css, theme):
    """Turn `@role name;` into that type role's declarations. Mono roles are uppercase, except code."""
    def one(match):
        role = match.group(1)
        spec = theme["type"][role]
        family = "var(--mono)" if spec.get("family") == "mono" else "var(--font)"
        out = (
            f"font-family:{family};font-size:var(--t-{role}-s);font-weight:var(--t-{role}-w);"
            f"letter-spacing:var(--t-{role}-tr);line-height:var(--t-{role}-lh);"
        )
        if spec.get("family") == "mono" and role != "code":
            out += "text-transform:uppercase;"
        return out

    return re.sub(r"@role (\w+);", one, css)



MIME = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp"}


def brand_parts(theme, base):
    """The brand mark for the page, or nothing. Returns (html, css_vars, notes). The logo files are
    embedded as base64, like the fonts. A theme with no logo, or a missing file, shows no mark."""
    brand = theme.get("brand") or {}
    notes = []

    def data_uri(name):
        if not name:
            return None
        path = Path(name)
        path = path if path.is_absolute() else Path(base) / path
        mime = MIME.get(path.suffix.lower())
        try:
            if not mime:
                raise ValueError(f"unsupported logo type {path.suffix or '(none)'}")
            return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
        except (OSError, ValueError) as exc:
            notes.append(f"logo not used: {exc} ({name})")
            return None

    light = data_uri(brand.get("logo"))
    if not light:
        return "", "", notes
    dark = data_uri(brand.get("logo_dark"))
    place = brand.get("placement", "above")
    place = place if place in ("above", "topleft") else "above"
    alt = html.escape(brand.get("alt", ""), quote=True)
    classes = f"brand {place}" + (" has-dark" if dark else "") + (" inv" if brand.get("invert_in_dark") else "")
    imgs = f'<img class="lg lg-light" src="{light}" alt="{alt}">'
    if dark:
        imgs += f'<img class="lg lg-dark" src="{dark}" alt="{alt}">'
    height = int(brand.get("height_px", 28))
    return f'<div class="{classes}">{imgs}</div>', f":root{{--brand-h:{height}px}}", notes


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Envato results: __TITLE__</title>
<style>
__FONT_FACES__
__THEME_VARS__
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);font-weight:var(--t-title-w);
       padding:32px var(--sp-pagex) var(--sp-pagebot)}
  header,.filters,.grid,footer{max-width:var(--sp-maxw);margin-inline:auto}
  header{display:flex;flex-direction:column;gap:var(--sp-hgap);margin-bottom:var(--sp-hmb);padding-top:var(--sp-pagetop)}
  .eyebrow{@role eyebrow;color:var(--accent-text)}
  .eyebrow::before{content:"_01 "}
  /* the theme sets the size (desktop and small screen); fitTitle() below only shrinks it when one word
     is too long for the line, and a word may break only if it still cannot fit at the smallest size */
  h1{margin:0;@role display;max-width:16ch;text-wrap:balance;overflow-wrap:anywhere;color:var(--ink)}
  .meta{@role meta;color:var(--muted);display:flex;flex-wrap:wrap;gap:4px 14px}
  .meta strong{color:var(--ink);font-weight:inherit}
  .filters{background:var(--surface);border:1px solid var(--border);border-radius:var(--sp-rcard);
           padding:var(--sp-fpady) var(--sp-fpadx);margin-bottom:var(--sp-fmb);display:flex;flex-wrap:wrap;
           gap:var(--sp-fgapy) var(--sp-fgapx)}
  .filters h2{flex-basis:100%;margin:0 0 4px;@role label;color:var(--muted)}
  details{min-width:0}
  details[open]{flex-basis:100%}
  summary{@role option;cursor:pointer;padding:4px 0;min-height:24px;color:var(--accent-text);transition:color .14s ease}
  /* our own open/closed arrow: the browser's marker disappears when summary is a flex row (touch sizes) */
  summary{list-style:none}
  summary::-webkit-details-marker{display:none}
  summary::before{content:"\25B8";display:inline-block;width:1.2em}
  details[open]>summary::before{content:"\25BE"}
  summary:focus-visible{color:var(--ink)}
  summary:active{color:var(--accent-text);text-decoration:underline}
  summary:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
  .chips{display:flex;flex-wrap:wrap;gap:var(--sp-chipgap);padding:4px 0 10px}
  .chip{@role label;padding:var(--sp-chipy) var(--sp-chipx);border:1px solid var(--border);
        border-radius:var(--sp-rchip);color:var(--muted)}
  .chip.on{background:var(--btn-bg);border-color:var(--btn-bg);color:var(--btn-ink)}
  .note{@role label;color:var(--muted);padding:2px 0 10px}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(var(--sp-cardmin),1fr));gap:var(--sp-gridgap)}
  .card{background:var(--surface);border:1px solid var(--border);border-radius:var(--sp-rcard);overflow:hidden;
        display:flex;flex-direction:column;min-width:0}
  .thumb{all:unset;display:block;cursor:zoom-in;position:relative}
  .thumb:focus-visible{outline:2px solid var(--focus);outline-offset:-2px}
  .thumb img{width:100%;aspect-ratio:4/3;object-fit:cover;display:block;background:var(--border)}
  .card-body{padding:var(--sp-cpadt) var(--sp-cpadx) var(--sp-cpadb);display:flex;flex-direction:column;
             gap:var(--sp-cgap);flex:1}
  .card-title{@role title;color:var(--ink);overflow-wrap:anywhere}
  .card-author{@role author;color:var(--muted)}
  .card-link,.lb-link{@role button;display:flex;align-items:center;justify-content:space-between;gap:var(--sp-btngap);
       text-decoration:none;transition:background-color .14s ease,color .14s ease}
  .card-link{margin-top:auto;align-self:stretch;padding:var(--sp-btny) var(--sp-btnx);border-radius:var(--sp-rbtn);
       background:transparent;color:var(--btn-bg);box-shadow:inset 0 0 0 1px var(--btn-bg)}
  .card-link::after,.lb-link::after{content:"\2197";color:var(--btn-arrow)}
  .card-link:focus-visible{background:var(--btn-bg);color:var(--btn-ink)}
  .card-link:active{background:color-mix(in srgb,var(--btn-bg) 82%,var(--bg));color:var(--btn-ink)}
  .card-link:focus-visible,.lb-link:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
  .lb{position:fixed;inset:0;background:var(--lb-bg);display:none;align-items:center;justify-content:center;
      flex-direction:column;gap:14px;padding:24px 16px;z-index:10}
  .lb[data-open="true"]{display:flex}
  .lb img{max-width:min(96vw,1200px);max-height:74vh;border-radius:var(--sp-rcard);background:var(--border)}
  .lb-cap{color:var(--ink-on-dark);text-align:center;max-width:720px;display:flex;flex-direction:column;gap:6px;align-items:center}
  .lb-title{@role title;color:var(--ink-on-dark)}
  .lb-author{@role author;color:var(--muted-on-dark)}
  .lb-link{color:var(--accent-on-dark);margin:0;gap:8px}
  .lb button{all:unset;cursor:pointer;color:var(--ink-on-dark);font-size:28px;line-height:1;padding:10px 14px;
             border-radius:var(--sp-rbtn);background:rgba(255,255,255,.1);position:absolute;min-width:44px;min-height:44px;
             display:inline-flex;align-items:center;justify-content:center;box-sizing:border-box}
  .lb button:focus-visible{outline:2px solid var(--ink-on-dark);outline-offset:2px}
  .lb .lb-close{top:14px;right:14px}
  .lb .lb-prev{left:12px;top:50%;transform:translateY(-50%)}
  .lb .lb-next{right:12px;top:50%;transform:translateY(-50%)}
  footer{@role label;color:var(--muted);margin-top:var(--sp-footmt);padding-top:var(--sp-footpt);border-top:1px solid var(--border)}
  .brand{display:flex;align-items:center}
  .brand img{height:var(--brand-h);width:auto;display:block}
  .brand.above{margin-bottom:8px}
  .brand.topleft{position:fixed;z-index:5;left:var(--sp-pagex);top:calc(14px + (38px - var(--brand-h)) / 2)}
  .brand .lg-dark{display:none}
  :root[data-theme="dark"] .brand.has-dark .lg-light{display:none}
  :root[data-theme="dark"] .brand.has-dark .lg-dark{display:block}
  :root[data-theme="dark"] .brand.inv .lg-light{filter:invert(1)}
  .themebar{position:fixed;top:14px;right:20px;z-index:5;display:flex;gap:2px;padding:3px;background:var(--bg);
            border:1px solid var(--border);border-radius:var(--sp-rbtn)}
  .themebar button{all:unset;box-sizing:border-box;cursor:pointer;width:32px;height:30px;display:inline-flex;
                   align-items:center;justify-content:center;color:var(--muted);border-radius:var(--sp-rbtn);
                   transition:color .14s ease}
  .themebar button svg{width:16px;height:16px;display:block}
  .themebar button[aria-pressed="true"]{background:var(--btn-bg);color:var(--btn-ink)}
  .themebar button:focus-visible{outline:2px solid var(--focus);outline-offset:1px}
  /* hover styles only where the device can hover: on touch, :hover sticks to the last thing tapped */
  @media (hover:hover){
    summary:hover:not(:active){color:var(--ink)}
    .card-link:hover:not(:active){background:var(--btn-bg);color:var(--btn-ink)}
    .lb button:hover{background:rgba(255,255,255,.22)}
    .themebar button:not([aria-pressed="true"]):hover{color:var(--accent-text)}
  }
  @media (pointer:coarse){
    .card-link,summary,.themebar button{min-height:44px}
    .themebar button{min-width:44px}
    summary{display:flex;align-items:center}
  }
  @media (prefers-reduced-motion:no-preference){.lb[data-open="true"]{animation:fade .12s ease-out}}
  @keyframes fade{from{opacity:0}}
</style>
<script>
  (function () {
    var mode = 'system';
    try { var saved = localStorage.getItem('gallery-mode'); if (saved === 'light' || saved === 'dark' || saved === 'system') mode = saved; } catch (e) {}
    var root = document.documentElement;
    root.dataset.mode = mode;
    root.dataset.theme = mode === 'system' ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : mode;
  })();
</script>
</head>
<body>
<div class="themebar" role="group" aria-label="Colour mode">
  <button type="button" data-mode="light" aria-pressed="false" aria-label="Light" title="Light"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12,2v2M12,20v2M4,12h-2M6.3,6.3l-1.4-1.4M17.7,6.3l1.4-1.4M6.3,17.7l-1.4,1.4M17.7,17.7l1.4,1.4M22,12h-2M17,12c0,2.8-2.2,5-5,5s-5-2.2-5-5,2.2-5,5-5,5,2.2,5,5Z"/></svg></button>
  <button type="button" data-mode="dark" aria-pressed="false" aria-label="Dark" title="Dark"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-miterlimit="10" stroke-width="1.5" d="M22,13c-1.4,2.4-4,4-7,4-4.4,0-8-3.6-8-8s1.6-5.6,4-7C6,2.5,2,6.8,2,12s4.5,10,10,10,9.5-4,10-9Z"/></svg></button>
  <button type="button" data-mode="system" aria-pressed="false" aria-label="System, follow the display setting" title="System"><svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M8 21H16M12 17V21M4 5C4 4.06812 4 3.60218 4.15224 3.23463C4.35523 2.74458 4.74458 2.35523 5.23463 2.15224C5.60218 2 6.06812 2 7 2H17C17.9319 2 18.3978 2 18.7654 2.15224C19.2554 2.35523 19.6448 2.74458 19.8478 3.23463C20 3.60218 20 4.06812 20 5V13C20 13.9319 20 14.3978 19.8478 14.7654C19.6448 15.2554 19.2554 15.6448 18.7654 15.8478C18.3978 16 17.9319 16 17 16H7C6.06812 16 5.60218 16 5.23463 15.8478C4.74458 15.6448 4.35523 15.2554 4.15224 14.7654C4 14.3978 4 13.9319 4 13V5Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
</div>
<header>
__BRAND__
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
  (function () {
    var root = document.documentElement, mq = matchMedia('(prefers-color-scheme: dark)');
    var buttons = document.querySelectorAll('.themebar button');
    function apply() {
      var mode = root.dataset.mode;
      root.dataset.theme = mode === 'system' ? (mq.matches ? 'dark' : 'light') : mode;
      buttons.forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.mode === mode); });
    }
    buttons.forEach(function (b) {
      b.addEventListener('click', function () {
        root.dataset.mode = b.dataset.mode;
        try { localStorage.setItem('gallery-mode', b.dataset.mode); } catch (e) {}
        apply();
      });
    });
    if (mq.addEventListener) mq.addEventListener('change', function () { if (root.dataset.mode === 'system') apply(); });
    apply();
  })();
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

// Title size: the theme's size is the guide. Shrink only when a single word is wider than the line,
// one pixel at a time, down to a floor. Runs again when the fonts load and when the window resizes.
(function(){
  var h=document.querySelector('h1'); if(!h) return; var FLOOR=24;
  function fitTitle(){
    h.style.fontSize=''; h.style.overflowWrap='normal';
    var size=parseFloat(getComputedStyle(h).fontSize);
    while(h.scrollWidth>h.clientWidth+0.5 && size>FLOOR){ size-=1; h.style.fontSize=size+'px'; }
    h.style.overflowWrap='';
  }
  fitTitle();
  if(document.fonts&&document.fonts.ready) document.fonts.ready.then(fitTitle);
  window.addEventListener('resize',fitTitle);
})();
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
    ap.add_argument("--theme", default=DEFAULT_THEME,
                    help=f"look of the page: a name in themes/ ({', '.join(available_themes()) or 'none'}) "
                         f"or a path to a theme .json (default: {DEFAULT_THEME})")
    ap.add_argument("--open", action="store_true", help="also open the page in the default browser")
    ap.add_argument("--no-serve", action="store_true", help="do not start the local server; print a file:// link")
    ap.add_argument("--no-open", action="store_true", help=argparse.SUPPRESS)  # old flag, now the default
    args = ap.parse_args()

    theme = load_theme(args.theme)
    if args.theme == DEFAULT_THEME:
        import check_theme_sync  # quick local file compare; silent when there is no master
        note = check_theme_sync.behind_note(THEMES_DIR / f"{DEFAULT_THEME}.json")
        if note:
            print(note, file=sys.stderr)
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

    faces, font_notes = font_faces(theme, SKILL_DIR)
    for note in font_notes:
        print(f"note: {note}")
    brand_html, brand_vars, brand_notes = brand_parts(theme, SKILL_DIR)
    for note in brand_notes:
        print(f"note: {note}")
    template = (
        TEMPLATE.replace("__FONT_FACES__", faces)
        .replace("__THEME_VARS__", theme_vars(theme) + brand_vars)
        .replace("__BRAND__", brand_html)
    )
    page = (
        expand_roles(template, theme).replace("__TITLE__", html.escape(spec.get("query", "search")))
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
