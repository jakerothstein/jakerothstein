#!/usr/bin/env python3
"""Generate the animated profile header SVGs (dark + light) into assets/.

Run:  python3 scripts/build_header.py
"""
import random
from pathlib import Path
from theme import THEMES, MONO, SANS, window, prompt_line, typed, fade, cursor

W, H = 900, 260
ABOUT = "CS @ Georgia Tech  ·  prev SWE Intern @ GitHub"
LOCATION = "Atlanta, GA  ·  127.0.0.1"


def build(theme):
    t = THEMES[theme]
    uid = "hdr"
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Jake Rothstein - {ABOUT}">']
    a = out.append
    a(f'<defs><linearGradient id="{uid}-name" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{t["name"]}"/><stop offset="1" stop-color="{t["accent2"]}"/></linearGradient></defs>')
    a(window(t, uid, W, H, "jake@github: ~", glow_pos=((760, 40, 220), (120, 260, 200))))

    x0, y = 28, 80
    s, now = prompt_line(t, uid, x0, y, "whoami", 0.3, size=15); a(s)
    now += 0.25
    name_y = y + 44
    a(fade(f'<text x="{x0}" y="{name_y}" font-family="{SANS}" font-size="40" font-weight="800" letter-spacing="-1" fill="url(#{uid}-name)">Jake Rothstein</text>', now))
    now += 0.55
    y2 = name_y + 40
    s, now = prompt_line(t, uid, x0, y2, "cat about.txt", now, size=15); a(s)
    now += 0.25
    y3 = y2 + 28
    s, now, _ = typed(ABOUT, x0, y3, 14, t["text"], now, cps=60, cid=f"{uid}-about"); a(s)
    now += 0.3
    y4 = y3 + 34
    s, now = prompt_line(t, uid, x0, y4, "git log --since=today", now, size=15); a(s)
    _, _, xend = typed("git log --since=today", x0 + 18, y4, 15, t["cmd"], 0)
    a(cursor(t, round(xend + 6, 1), y4, now))

    # Contribution-grid accent (right side): lights up in a wave, then shimmers
    gx, gy, cell, gap, cols, rows = 560, 62, 15, 4, 16, 7
    rnd = random.Random(42)
    for c in range(cols):
        for r in range(rows):
            x, yy = gx + c * (cell + gap), gy + r * (cell + gap)
            lvl = rnd.choice([0, 0, 0, 1, 1, 2, 2, 3])
            delay = round(0.9 + c * 0.09 + r * 0.03, 2)
            a(f'<rect x="{x}" y="{yy}" width="{cell}" height="{cell}" rx="3" fill="{t["cell"]}" stroke="{t["cell_border"]}" stroke-width="0.5"/>')
            if lvl:
                shimmer = f'<animate attributeName="opacity" values="1;0.55;1" dur="{round(2.5 + rnd.random()*2.5,2)}s" begin="{delay + 1.2}s" repeatCount="indefinite"/>' if lvl >= 2 else ""
                a(f'<rect x="{x}" y="{yy}" width="{cell}" height="{cell}" rx="3" fill="{t["levels"][lvl-1]}" opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.5s" begin="{delay}s" fill="freeze"/>{shimmer}</rect>')
    ly = gy + rows * (cell + gap) + 18
    a(f'<text x="{gx}" y="{ly}" font-family="{MONO}" font-size="11" fill="{t["muted"]}">{LOCATION}</text>')
    a(f'<g font-family="{MONO}" font-size="11" fill="{t["muted"]}"><text x="{gx + 205}" y="{ly}">less</text>')
    for i, lv in enumerate(t["levels"]):
        a(f'<rect x="{gx + 240 + i*14}" y="{ly - 9}" width="10" height="10" rx="2" fill="{lv}"/>')
    a(f'<text x="{gx + 300}" y="{ly}">more</text></g>')
    a('</svg>')
    return "\n".join(out)


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent.parent / "assets"
    for theme in THEMES:
        p = out_dir / f"header-{theme}.svg"
        p.write_text(build(theme))
        print(f"wrote {p.relative_to(out_dir.parent)} ({p.stat().st_size} bytes)")
