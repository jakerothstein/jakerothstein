"""Shared look-and-feel for every generated SVG (header + stat cards).

Pure SVG + SMIL, no external fonts/scripts, so everything renders through
GitHub's README image proxy in both light and dark mode.
"""

import zlib

MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"

THEMES = {
    "dark": dict(
        bg0="#0d1117", bg1="#161b22", border="#30363d", grid="#ffffff", grid_op="0.035",
        text="#e6edf3", muted="#8b949e", faint="#484f58", prompt="#3fb950", cmd="#79c0ff", name="#ffffff",
        accent="#a371f7", accent2="#39d3f2", glow1="0.55", glow2="0.45",
        cell="#161b22", cell_border="#30363d", track="#21262d",
        levels=["#0e4429", "#006d32", "#26a641", "#39d353"],
        dots=("#ff5f57", "#febc2e", "#28c840"),
        warn="#d29922", pr="#a371f7", issue="#3fb950", star="#e3b341", push="#79c0ff", create="#39d3f2",
    ),
    "light": dict(
        bg0="#ffffff", bg1="#f6f8fa", border="#d0d7de", grid="#000000", grid_op="0.045",
        text="#1f2328", muted="#57606a", faint="#8c959f", prompt="#1a7f37", cmd="#0550ae", name="#0d1117",
        accent="#8250df", accent2="#0969da", glow1="0.22", glow2="0.18",
        cell="#ebedf0", cell_border="#d0d7de", track="#eaeef2",
        levels=["#9be9a8", "#40c463", "#30a14e", "#216e39"],
        dots=("#ff5f57", "#febc2e", "#28c840"),
        warn="#9a6700", pr="#8250df", issue="#1a7f37", star="#bf8700", push="#0969da", create="#0969da",
    ),
}


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def defs(t, uid, w, h, glow=True):
    g = ""
    if glow:
        g = f"""
  <radialGradient id="{uid}-glow1"><stop offset="0" stop-color="{t['accent']}" stop-opacity="{t['glow1']}"/><stop offset="1" stop-color="{t['accent']}" stop-opacity="0"/></radialGradient>
  <radialGradient id="{uid}-glow2"><stop offset="0" stop-color="{t['accent2']}" stop-opacity="{t['glow2']}"/><stop offset="1" stop-color="{t['accent2']}" stop-opacity="0"/></radialGradient>"""
    return f"""<defs>
  <linearGradient id="{uid}-bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t['bg0']}"/><stop offset="1" stop-color="{t['bg1']}"/></linearGradient>{g}
  <pattern id="{uid}-dots" width="18" height="18" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="1.2" fill="{t['grid']}" fill-opacity="{t['grid_op']}"/></pattern>
  <clipPath id="{uid}-card"><rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="16"/></clipPath>
</defs>"""


def window(t, uid, w, h, title, glow=True, glow_pos=None):
    """Card background + macOS-style window chrome. Returns SVG fragment."""
    out = [defs(t, uid, w, h, glow)]
    out.append(f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="16" fill="url(#{uid}-bg)" stroke="{t["border"]}"/>')
    out.append(f'<g clip-path="url(#{uid}-card)"><rect width="{w}" height="{h}" fill="url(#{uid}-dots)"/>')
    if glow:
        (x1, y1, r1), (x2, y2, r2) = glow_pos or ((w - 140, 40, 220), (120, h, 200))
        out.append(f'<circle cx="{x1}" cy="{y1}" r="{r1}" fill="url(#{uid}-glow1)"><animateTransform attributeName="transform" type="translate" values="0 0;-40 30;0 0" dur="14s" repeatCount="indefinite"/></circle>')
        out.append(f'<circle cx="{x2}" cy="{y2}" r="{r2}" fill="url(#{uid}-glow2)"><animateTransform attributeName="transform" type="translate" values="0 0;50 -20;0 0" dur="17s" repeatCount="indefinite"/></circle>')
    out.append('</g>')
    for i, c in enumerate(t["dots"]):
        out.append(f'<circle cx="{26 + i*18}" cy="24" r="5.5" fill="{c}"/>')
    out.append(f'<text x="{w/2}" y="28" text-anchor="middle" font-family="{MONO}" font-size="12" fill="{t["muted"]}">{esc(title)}</text>')
    out.append(f'<line x1="0.5" y1="44" x2="{w-0.5}" y2="44" stroke="{t["border"]}"/>')
    return "\n".join(out)


def typed(text, x, y, size, color, begin, cps=22, family=MONO, weight="400", cid="clip"):
    """A <text> revealed one character at a time via a discrete clip animation.
    Returns (svg, end_time, end_x)."""
    n = max(len(text), 1)
    cw = size * 0.602  # monospace advance width; enforced via textLength
    width = round(n * cw, 2)
    dur = round(n / cps, 3)
    values = ";".join(f"{round(i * cw, 2)}" for i in range(n + 1))
    key_times = ";".join(f"{round(i / n, 4)}" for i in range(n + 1))
    svg = f"""
  <clipPath id="{cid}"><rect x="{x}" y="{y - size}" height="{size * 1.4}" width="0">
    <animate attributeName="width" values="{values}" keyTimes="{key_times}" calcMode="discrete" dur="{dur}s" begin="{begin}s" fill="freeze"/>
  </rect></clipPath>
  <text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" fill="{color}" textLength="{width}" lengthAdjust="spacing" clip-path="url(#{cid})">{esc(text)}</text>"""
    return svg, round(begin + dur, 3), round(x + width, 2)


def prompt_line(t, uid, x, y, cmd, begin, size=14):
    """'$ cmd' typed out. Returns (svg, end_time)."""
    p = f'<text x="{x}" y="{y}" font-family="{MONO}" font-size="{size}" fill="{t["prompt"]}">$</text>'
    s, end, _ = typed(cmd, x + 18, y, size, t["cmd"], begin, cid=f"{uid}-{zlib.crc32(cmd.encode()):08x}")
    return p + s, end


def fade(inner, begin, dur=0.35):
    return f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" dur="{dur}s" begin="{begin}s" fill="freeze"/>{inner}</g>'


def cursor(t, x, y, begin, size=15):
    return f'<rect x="{x}" y="{y - size + 2}" width="{size*0.6}" height="{size + 2}" rx="1.5" fill="{t["cmd"]}" opacity="0"><animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1.1s" begin="{begin}s" repeatCount="indefinite"/></rect>'


def fmt(n):
    n = int(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n/1000:.1f}k"
    return f"{n:,}"
