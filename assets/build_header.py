#!/usr/bin/env python3
"""Generate the animated profile header SVGs (dark + light) in this folder.

Run:  python3 assets/build_header.py
Pure SVG + SMIL animations, no external fonts or scripts, so it renders
inside GitHub's README <img> proxy.
"""
from pathlib import Path

W, H = 900, 260
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"

THEMES = {
    "dark": dict(
        bg0="#0d1117", bg1="#161b22", border="#30363d", grid="#ffffff", grid_op="0.035",
        text="#e6edf3", muted="#8b949e", prompt="#3fb950", cmd="#79c0ff", name="#ffffff",
        accent="#a371f7", accent2="#39d3f2", glow1="0.55", glow2="0.45",
        cell="#161b22", cell_border="#30363d",
        levels=["#0e4429", "#006d32", "#26a641", "#39d353"],
        dots=("#ff5f57", "#febc2e", "#28c840"),
    ),
    "light": dict(
        bg0="#ffffff", bg1="#f6f8fa", border="#d0d7de", grid="#000000", grid_op="0.045",
        text="#1f2328", muted="#57606a", prompt="#1a7f37", cmd="#0550ae", name="#0d1117",
        accent="#8250df", accent2="#0969da", glow1="0.22", glow2="0.18",
        cell="#ebedf0", cell_border="#d0d7de",
        levels=["#9be9a8", "#40c463", "#30a14e", "#216e39"],
        dots=("#ff5f57", "#febc2e", "#28c840"),
    ),
}


def typed(text, x, y, size, color, begin, cps=22, family=MONO, weight="400", cid=None):
    """A <text> revealed one character at a time via a discrete clip animation."""
    n = len(text)
    cw = size * 0.602  # monospace advance width; enforced via textLength
    width = round(n * cw, 2)
    dur = round(n / cps, 3)
    values = ";".join(f"{round(i * cw, 2)}" for i in range(n + 1))
    key_times = ";".join(f"{round(i / n, 4)}" for i in range(n + 1))
    cid = cid or f"clip{abs(hash((text, x, y)))}"
    esc = text.replace("&", "&amp;").replace("<", "&lt;")
    return f"""
  <clipPath id="{cid}"><rect x="{x}" y="{y - size}" height="{size * 1.4}" width="0">
    <animate attributeName="width" values="{values}" keyTimes="{key_times}" calcMode="discrete" dur="{dur}s" begin="{begin}s" fill="freeze"/>
  </rect></clipPath>
  <text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" fill="{color}" textLength="{width}" lengthAdjust="spacing" clip-path="url(#{cid})">{esc}</text>""", begin + dur, x + width


def fade(inner, begin):
    return f"""<g opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.35s" begin="{begin}s" fill="freeze"/>{inner}</g>"""


def build(theme):
    t = THEMES[theme]
    out = []
    a = out.append

    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Jake Rothstein - CS at Georgia Tech, previously SWE Intern at GitHub">')
    a(f"""<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t['bg0']}"/><stop offset="1" stop-color="{t['bg1']}"/></linearGradient>
  <radialGradient id="glow1"><stop offset="0" stop-color="{t['accent']}" stop-opacity="{t['glow1']}"/><stop offset="1" stop-color="{t['accent']}" stop-opacity="0"/></radialGradient>
  <radialGradient id="glow2"><stop offset="0" stop-color="{t['accent2']}" stop-opacity="{t['glow2']}"/><stop offset="1" stop-color="{t['accent2']}" stop-opacity="0"/></radialGradient>
  <pattern id="dots" width="18" height="18" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="1.2" fill="{t['grid']}" fill-opacity="{t['grid_op']}"/></pattern>
  <clipPath id="card"><rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="16"/></clipPath>
  <linearGradient id="nameGrad" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{t['name']}"/><stop offset="1" stop-color="{t['accent2']}"/></linearGradient>
</defs>""")

    # Card + background
    a(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="16" fill="url(#bg)" stroke="{t["border"]}"/>')
    a('<g clip-path="url(#card)">')
    a(f'<rect width="{W}" height="{H}" fill="url(#dots)"/>')
    # Drifting glows
    a(f"""<circle cx="760" cy="40" r="220" fill="url(#glow1)"><animateTransform attributeName="transform" type="translate" values="0 0;-40 30;0 0" dur="14s" repeatCount="indefinite"/></circle>
<circle cx="120" cy="260" r="200" fill="url(#glow2)"><animateTransform attributeName="transform" type="translate" values="0 0;50 -20;0 0" dur="17s" repeatCount="indefinite"/></circle>""")
    a('</g>')

    # Window chrome
    a('<g>')
    for i, c in enumerate(t["dots"]):
        a(f'<circle cx="{26 + i*18}" cy="24" r="5.5" fill="{c}"/>')
    a(f'<text x="{W/2}" y="28" text-anchor="middle" font-family="{MONO}" font-size="12" fill="{t["muted"]}">jake@github: ~</text>')
    a(f'<line x1="0.5" y1="44" x2="{W-0.5}" y2="44" stroke="{t["border"]}"/>')
    a('</g>')

    # Terminal script
    x0, y = 28, 80
    tnow = 0.3
    a(f'<text x="{x0}" y="{y}" font-family="{MONO}" font-size="15" fill="{t["prompt"]}">$</text>')
    s, tnow, _ = typed("whoami", x0 + 18, y, 15, t["cmd"], tnow)
    a(s)
    tnow += 0.25
    name_y = y + 44
    a(fade(f'<text x="{x0}" y="{name_y}" font-family="{SANS}" font-size="40" font-weight="800" letter-spacing="-1" fill="url(#nameGrad)">Jake Rothstein</text>', tnow))
    tnow += 0.55

    y2 = name_y + 40
    a(f'<text x="{x0}" y="{y2}" font-family="{MONO}" font-size="15" fill="{t["prompt"]}">$</text>')
    s, tnow, _ = typed("cat about.txt", x0 + 18, y2, 15, t["cmd"], tnow)
    a(s)
    tnow += 0.25
    y3 = y2 + 28
    about = "CS @ Georgia Tech  ·  prev SWE Intern @ GitHub"
    s, tnow, _ = typed(about, x0, y3, 14, t["text"], tnow, cps=60)
    a(s)
    tnow += 0.3

    y4 = y3 + 34
    a(f'<text x="{x0}" y="{y4}" font-family="{MONO}" font-size="15" fill="{t["prompt"]}">$</text>')
    s, tnow, xend = typed("git log --since=today", x0 + 18, y4, 15, t["cmd"], tnow)
    a(s)
    # Blinking block cursor after the last command
    a(f'<rect x="{round(xend + 6, 1)}" y="{y4 - 13}" width="9" height="17" rx="1.5" fill="{t["cmd"]}" opacity="0"><animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1.1s" begin="{round(tnow,2)}s" repeatCount="indefinite"/></rect>')

    # Contribution-grid accent (right side), lights up in a wave then keeps a slow shimmer
    gx, gy, cell, gap = 560, 62, 15, 4
    cols, rows = 16, 7
    import random
    rnd = random.Random(42)
    a(f'<g>')
    for c in range(cols):
        for r in range(rows):
            x = gx + c * (cell + gap)
            yy = gy + r * (cell + gap)
            lvl = rnd.choice([0, 0, 0, 1, 1, 2, 2, 3])
            col = t["cell"] if lvl == 0 else t["levels"][lvl - 1]
            delay = round(0.9 + c * 0.09 + r * 0.03, 2)
            shimmer = ""
            if lvl >= 2:
                shimmer = f'<animate attributeName="opacity" values="1;0.55;1" dur="{round(2.5 + rnd.random()*2.5,2)}s" begin="{delay + 1.2}s" repeatCount="indefinite"/>'
            a(f'<rect x="{x}" y="{yy}" width="{cell}" height="{cell}" rx="3" fill="{t["cell"]}" stroke="{t["cell_border"]}" stroke-width="0.5"/>')
            if lvl:
                a(f'<rect x="{x}" y="{yy}" width="{cell}" height="{cell}" rx="3" fill="{col}" opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.5s" begin="{delay}s" fill="freeze"/>{shimmer}</rect>')
    a('</g>')
    # Caption under grid
    a(f'<text x="{gx}" y="{gy + rows*(cell+gap) + 18}" font-family="{MONO}" font-size="11" fill="{t["muted"]}">Atlanta, GA  ·  127.0.0.1</text>')
    a(f'<g font-family="{MONO}" font-size="11" fill="{t["muted"]}"><text x="{gx + 205}" y="{gy + rows*(cell+gap) + 18}">less</text>')
    for i, lv in enumerate(t["levels"]):
        a(f'<rect x="{gx + 240 + i*14}" y="{gy + rows*(cell+gap) + 9}" width="10" height="10" rx="2" fill="{lv}"/>')
    a(f'<text x="{gx + 300}" y="{gy + rows*(cell+gap) + 18}">more</text></g>')

    a('</svg>')
    return "\n".join(out)


if __name__ == "__main__":
    here = Path(__file__).parent
    for theme in THEMES:
        p = here / f"header-{theme}.svg"
        p.write_text(build(theme))
        print(f"wrote {p} ({p.stat().st_size} bytes)")
