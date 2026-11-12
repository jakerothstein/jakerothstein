#!/usr/bin/env python3
"""Render the generated elements of the profile README (dark + light) into
assets/: an isometric, monochrome contribution "skyline" and a small, quiet
languages chart.

Only public data is read, so the built-in Actions token is enough.

Run:  GH_TOKEN=$(gh auth token) python3 scripts/build_cards.py
"""
import json
import math
import os
import urllib.request
from pathlib import Path

LOGIN = os.environ.get("PROFILE_USER", "jakerothstein")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
API = "https://api.github.com"
OUT = Path(__file__).resolve().parent.parent / "assets"
MAX_LANGS = 8   # anything past this is folded into "Other"

# No external fonts inside an SVG served as an image: system stack only.
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"

# GitHub's own foreground/border tokens. The background is left transparent so
# the chart sits directly on the page in every GitHub theme.
THEMES = {
    "light": dict(text="#1f2328", muted="#59636e", hi="#1f2328", lo="#d1d9e0"),
    "dark": dict(text="#f0f6fc", muted="#9198a1", hi="#f0f6fc", lo="#3d444d"),
}

# Both charts share one natural width and are shown at the full README width.
W = 760


def _req(url, data=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-cards"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    body = json.dumps(data).encode() if data is not None else None
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode()), r.headers.get("Link", "")


def own_repos():
    """Public, original (not forked, not archived) repositories."""
    url = f"{API}/users/{LOGIN}/repos?per_page=100&type=owner"
    repos = []
    while url:
        page, link = _req(url)
        repos.extend(page)
        url = None
        for part in link.split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
    return [r for r in repos if not r["fork"] and not r["archived"]]


def fetch_languages():
    """Bytes of code per language across own public repos."""
    repos = own_repos()
    langs = {}
    for i in range(0, len(repos), 40):
        chunk = repos[i:i + 40]
        query = "query {" + " ".join(
            f'r{j}: repository(owner:{json.dumps(LOGIN)}, name:{json.dumps(r["name"])}) '
            f'{{ languages(first:12, orderBy:{{field:SIZE, direction:DESC}}) {{ edges {{ size node {{ name }} }} }} }}'
            for j, r in enumerate(chunk)) + "}"
        data, _ = _req(f"{API}/graphql", {"query": query})
        if data.get("errors"):
            # Fail rather than publish a chart built from partial data.
            raise RuntimeError(json.dumps(data["errors"])[:500])
        for repo in data["data"].values():
            for e in ((repo or {}).get("languages") or {}).get("edges", []):
                name = e["node"]["name"]
                langs[name] = langs.get(name, 0) + e["size"]
    return len(repos), langs


def rows_from(langs):
    """[(name, share 0..1)] for every language, largest first; the tail becomes "Other"."""
    total = sum(langs.values())
    if not total:
        return []
    ranked = sorted(langs.items(), key=lambda x: (-x[1], x[0]))
    rows = [(n, b / total) for n, b in ranked[:MAX_LANGS]]
    rest = sum(b for _, b in ranked[MAX_LANGS:])
    if rest:
        rows.append(("Other", rest / total))
    return rows


def fetch_calendar():
    """(total, weeks) for the last year; weeks = [[(weekday, count, 'YYYY-MM-DD'), ...], ...]."""
    query = ("query { user(login:%s) { contributionsCollection { contributionCalendar { totalContributions "
             "weeks { contributionDays { contributionCount date weekday } } } } } }" % json.dumps(LOGIN))
    data, _ = _req(f"{API}/graphql", {"query": query})
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"])[:500])
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [[(d["weekday"], d["contributionCount"], d["date"]) for d in w["contributionDays"]] for w in cal["weeks"]]
    return cal["totalContributions"], weeks


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _text_w(s, size):
    """Estimated width of s in a system sans; SVG-as-image cannot measure text."""
    em = 0.0
    for ch in s:
        em += (0.27 if ch in "iljtfr. '" else 0.82 if ch in "mwMW%" else 0.66 if ch.isupper()
               else 0.6 if ch in "<+#" else 0.55)
    return em * size


def _pct(share):
    return "<1%" if share < 0.005 else f"{round(share * 100)}%"


def render(t, rows):
    """One full-width stacked bar, darkest-to-lightest by share, with a legend beneath."""
    BAR_Y, BAR_H, GAP, MIN_SEG = 26, 8, 2, 3
    FS, LINE, DOT = 13, 24, 8
    n = len(rows)
    shades = [_mix(t["hi"], t["lo"], i / max(n - 1, 1)) for i in range(n)]
    label = "Languages by share of public code: " + ", ".join(f"{n_} {_pct(s_)}" for n_, s_ in rows)
    body = [f'<text x="0" y="12" font-size="12" fill="{t["muted"]}">Languages</text>']
    if not rows:
        body.append(f'<text x="0" y="{BAR_Y + 14}" font-size="{FS}" fill="{t["muted"]}">No public code yet</text>')
    # Bar: every segment gets a visible minimum, the largest absorbs the difference.
    avail = W - GAP * max(n - 1, 0)
    widths = [max(avail * s_, MIN_SEG) for _, s_ in rows]
    if widths:
        widths[0] -= sum(widths) - avail
    x = 0.0
    clip = f'<clipPath id="bar"><rect x="0" y="{BAR_Y}" width="{W}" height="{BAR_H}" rx="{BAR_H / 2}"/></clipPath>'
    body.append('<g clip-path="url(#bar)">')
    for w_, shade in zip(widths, shades):
        body.append(f'<rect x="{x:.1f}" y="{BAR_Y}" width="{w_:.1f}" height="{BAR_H}" fill="{shade}"/>')
        x += w_ + GAP
    body.append("</g>")
    # Legend: flows left to right and wraps.
    x, y = 0.0, BAR_Y + BAR_H + 26
    for (name, share), shade in zip(rows, shades):
        pct = _pct(share)
        item_w = DOT + 7 + _text_w(name, FS) + 6 + _text_w(pct, FS)
        if x and x + item_w > W:
            x, y = 0.0, y + LINE
        body.append(f'<rect x="{x:.1f}" y="{y - DOT - 1}" width="{DOT}" height="{DOT}" rx="2" fill="{shade}"/>')
        body.append(f'<text x="{x + DOT + 7:.1f}" y="{y}" font-size="{FS}"><tspan fill="{t["text"]}">{esc(name)}</tspan>'
                    f'<tspan dx="6" fill="{t["muted"]}">{pct}</tspan></text>')
        x += item_w + 22
    h = y + 8
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" aria-label="{esc(label)}">',
        f"<defs>{clip}</defs>", f'<g font-family="{SANS}">', *body, "</g>", "</svg>"]) + "\n"


# --- Contribution skyline -------------------------------------------------
# The year as a field of columns: one per day, height = contributions. Drawn
# in a shallow axonometric view so it stays a wide, low strip. One hue only.
SKY = {
    # page: assumed page colour the sides fade toward (the SVG itself is transparent)
    "light": dict(page="#ffffff", tile="#eceff2", lo="#b7c0c9", hi="#1f2328", muted="#59636e"),
    "dark": dict(page="#0d1117", tile="#1a2028", lo="#5d6671", hi="#f0f6fc", muted="#9198a1"),
}
SKY_W = W
PITCH, CELL = 13.2, 0.76         # grid pitch in px, tile size as a share of it
YAW, TILT = math.radians(9), math.radians(42)
H_MIN, H_MAX = 2.5, 46           # column height range in px
# Seconds: pause before anything moves (so the page has settled and the eye has
# arrived), the left-to-right stagger, and each column's own rise.
HOLD, SWEEP, RISE = 0.9, 2.0, 1.0
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
# Screen-space unit vectors for the week axis, the weekday axis and "up".
WX, WY = math.cos(YAW), math.sin(YAW) * math.sin(TILT)
DX, DY = -math.sin(YAW), math.cos(YAW) * math.sin(TILT)
UP = math.cos(TILT)


def _mix(a, b, k):
    """Blend hex colour a toward b by k (0..1)."""
    ca, cb = (int(a[i:i + 2], 16) for i in (1, 3, 5)), (int(b[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(x + (y - x) * k):02x}" for x, y in zip(ca, cb))


def _pt(w, d, z=0.0):
    return (PITCH * (w * WX + d * DX), PITCH * (w * WY + d * DY) - z * UP)


def render_skyline(t, total, weeks):
    peak = max((c for wk in weeks for _, c, _ in wk), default=0) or 1
    polys, labels = [], []
    prev_month, last_label_w = None, -9
    for w, days in enumerate(weeks):
        month = int(days[0][2][5:7])
        if month != prev_month:
            # Skip a label that would collide with the previous one or hang off the end.
            if w >= 1 and w - last_label_w >= 3 and w <= len(weeks) - 2:
                labels.append((_pt(w, 7.9), MONTHS[month - 1]))
                last_label_w = w
            prev_month = month
        for d, count, _ in days:
            k = (count / peak) ** 0.55 if count else 0.0
            z = H_MIN + k * (H_MAX - H_MIN) if count else 0.0
            top = _mix(t["lo"], t["hi"], k) if count else t["tile"]
            a, b, c, e = (_pt(w, d, z), _pt(w + CELL, d, z), _pt(w + CELL, d + CELL, z), _pt(w, d + CELL, z))
            a0, b0, c0, e0 = _pt(w, d), _pt(w + CELL, d), _pt(w + CELL, d + CELL), _pt(w, d + CELL)
            # Each entry: (final outline, fill, outline while flat on the floor, week).
            if count:
                polys.append(((e, c, c0, e0), _mix(top, t["page"], 0.42), (e0, c0, c0, e0), w))  # face toward the viewer
                polys.append(((b, c, c0, b0), _mix(top, t["page"], 0.66), (b0, c0, c0, b0), w))  # face toward the year's end
                polys.append(((a, b, c, e), top, (a0, b0, c0, e0), w))
            else:
                polys.append(((a, b, c, e), top, None, w))
    xs = [x for pts, *_ in polys for x, _ in pts]
    ys = [y for pts, *_ in polys for _, y in pts]
    head = 30                                    # room for the caption
    scale = SKY_W / (max(xs) - min(xs))
    ox, oy = -min(xs), -min(ys)
    h = math.ceil(head + (max(ys) - min(ys)) * scale + 22)
    label = f"{total:,} contributions in the last year, drawn as an isometric field of columns, one per day"
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SKY_W}" height="{h}" viewBox="0 0 {SKY_W} {h}" role="img" aria-label="{esc(label)}">',
        f'<g font-family="{SANS}" fill="{t["muted"]}">',
        f'<text x="0" y="12" font-size="12">{total:,} contributions in the last year</text>',
    ]
    for (x, y), name in labels:
        out.append(f'<text x="{(x + ox) * scale:.1f}" y="{head + (y + oy) * scale + 9:.1f}" font-size="10.5" text-anchor="middle">{name}</text>')
    out.append("</g>")
    out.append(f'<g transform="translate(0 {head}) scale({scale:.4f}) translate({ox:.2f} {oy:.2f})">')
    def d_of(pts):
        return "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z"

    for pts, fill, flat, w in polys:
        if flat is None:
            out.append(f'<path fill="{fill}" d="{d_of(pts)}"/>')
            continue
        # Rise once from the floor, sweeping left to right; the resting state is
        # the path's own d, so viewers without SMIL just see the finished chart.
        start = HOLD + SWEEP * w / max(len(weeks) - 1, 1)
        dur = start + RISE
        out.append(f'<path fill="{fill}" d="{d_of(pts)}"><animate attributeName="d" dur="{dur:.2f}s" calcMode="spline" '
                   f'keyTimes="0;{start / dur:.3f};1" keySplines="0 0 1 1;0.16 1 0.3 1" '
                   f'values="{d_of(flat)};{d_of(flat)};{d_of(pts)}"/></path>')
    out += ["</g>", "</svg>"]
    return "\n".join(out) + "\n"


def main():
    n_repos, langs = fetch_languages()
    rows = rows_from(langs)
    print(f"fetched: {n_repos} own repos, {len(langs)} languages")
    total, weeks = fetch_calendar()
    print(f"fetched: {total} contributions over {len(weeks)} weeks")
    OUT.mkdir(exist_ok=True)
    for theme, t in THEMES.items():
        for name, svg in (("languages", render(t, rows)), ("skyline", render_skyline(SKY[theme], total, weeks))):
            p = OUT / f"{name}-{theme}.svg"
            p.write_text(svg)
            print(f"wrote {p.relative_to(OUT.parent)} ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
