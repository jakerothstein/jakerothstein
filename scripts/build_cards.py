#!/usr/bin/env python3
"""Fetch GitHub data and render the profile stat cards (dark + light) into assets/.

Works with the built-in Actions token (public data only) or a PAT in
GH_TOKEN / GITHUB_TOKEN for private contribution counts.

Run:  GH_TOKEN=$(gh auth token) python3 scripts/build_cards.py
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path

from theme import THEMES, MONO, SANS, window, prompt_line, fade, cursor, esc, fmt

LOGIN = os.environ.get("PROFILE_USER", "jakerothstein")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
API = "https://api.github.com"
OUT = Path(__file__).resolve().parent.parent / "assets"
IGNORED_LANGS = {"HTML", "CSS", "SCSS", "Makefile", "Shell", "Dockerfile", "CMake", "Batchfile", "PowerShell"}
FULL_W, HALF_W = 900, 440


# ─────────────────────────────── GitHub API ───────────────────────────────
def _req(url, data=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": f"{LOGIN}-profile-cards"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    body = json.dumps(data).encode() if data is not None else None
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        link = r.headers.get("Link", "")
        return json.loads(r.read().decode()), link


def rest(path, paginate=False):
    url = f"{API}{path}"
    if not paginate:
        return _req(url)[0]
    items = []
    while url:
        page, link = _req(url)
        items.extend(page)
        url = None
        for part in link.split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
    return items


def graphql(query, variables):
    data = _req(f"{API}/graphql", {"query": query, "variables": variables})[0]
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"])[:500])
    return data["data"]


def fetch():
    today = dt.date.today()
    since = today - dt.timedelta(days=364)
    user = rest(f"/users/{LOGIN}")
    repos = [r for r in rest(f"/users/{LOGIN}/repos?per_page=100&type=owner&sort=pushed", paginate=True)]
    own = [r for r in repos if not r["fork"] and not r["archived"]]

    contrib = graphql("""
      query($login:String!, $from:DateTime!, $to:DateTime!) {
        user(login:$login) {
          contributionsCollection(from:$from, to:$to) {
            totalCommitContributions totalPullRequestContributions
            totalIssueContributions totalPullRequestReviewContributions
            restrictedContributionsCount
            contributionCalendar { totalContributions weeks { contributionDays { date contributionCount contributionLevel } } }
          }
        }
      }""", {"login": LOGIN, "from": f"{since}T00:00:00Z", "to": f"{today}T23:59:59Z"})["user"]["contributionsCollection"]

    # Languages by bytes across own public repos (batched GraphQL, aliases)
    langs, colors = {}, {}
    for i in range(0, len(own), 40):
        chunk = own[i:i + 40]
        q = "query {" + " ".join(
            f'r{j}: repository(owner:"{LOGIN}", name:"{r["name"]}") {{ languages(first:12, orderBy:{{field:SIZE, direction:DESC}}) {{ edges {{ size node {{ name color }} }} }} }}'
            for j, r in enumerate(chunk)) + "}"
        try:
            data = graphql(q, {})
        except Exception as e:  # keep going with what we have
            print(f"warn: language query failed: {e}", file=sys.stderr)
            continue
        for v in data.values():
            for e in ((v or {}).get("languages") or {}).get("edges", []):
                n = e["node"]["name"]
                langs[n] = langs.get(n, 0) + e["size"]
                colors[n] = e["node"]["color"] or "#8b949e"

    try:
        events = rest(f"/users/{LOGIN}/events/public?per_page=100")
    except Exception as e:
        print(f"warn: events failed: {e}", file=sys.stderr)
        events = []

    return dict(user=user, repos=repos, own=own, contrib=contrib, langs=langs, colors=colors, events=events, today=today)


# ─────────────────────────────── derived stats ───────────────────────────────
def streaks(days, today):
    """days: list of (date, count) ascending. Returns (current, longest, busiest)."""
    cur = longest = run = 0
    busiest = (None, 0)
    for d, c in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
        if c > busiest[1]:
            busiest = (d, c)
    # current streak: count back from today (or yesterday if today has nothing yet)
    by_date = dict(days)
    d = today
    if by_date.get(d, 0) == 0:
        d -= dt.timedelta(days=1)
    while by_date.get(d, 0) > 0:
        cur += 1
        d -= dt.timedelta(days=1)
    return cur, longest, busiest


def rel_time(iso, now):
    then = dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    # Day granularity on purpose: the cards are rebuilt every few hours and
    # should only change when something actually happened.
    s = int((now - then).total_seconds())
    if s < 86400:
        return "today"
    for unit, secs in (("y", 31536000), ("mo", 2592000), ("w", 604800), ("d", 86400)):
        if s >= secs:
            return f"{s // secs}{unit} ago"
    return "today"


def summarize_events(events, limit=6):
    """Collapse the public event stream into human lines (merging consecutive pushes)."""
    now = dt.datetime.now(dt.timezone.utc)
    lines = []
    for ev in events:
        if ev["repo"]["name"].lower() == f"{LOGIN}/{LOGIN}".lower():
            continue  # this profile repo: its refresh commits are noise
        repo = ev["repo"]["name"].split("/", 1)[-1]
        p = ev.get("payload", {})
        kind = ev["type"]
        if kind == "PushEvent":
            n = len(p.get("commits", [])) or p.get("size", 1)
            if lines and lines[-1]["kind"] == "push" and lines[-1]["repo"] == repo:
                lines[-1]["n"] += n
                continue
            lines.append(dict(kind="push", repo=repo, n=n, when=ev["created_at"]))
        elif kind == "PullRequestEvent" and p.get("action") in ("opened", "closed"):
            merged = p.get("action") == "closed" and p["pull_request"].get("merged")
            if p.get("action") == "closed" and not merged:
                continue
            lines.append(dict(kind="pr", repo=repo, n=p["pull_request"]["number"], verb="merged" if merged else "opened", when=ev["created_at"]))
        elif kind == "IssuesEvent" and p.get("action") == "opened":
            lines.append(dict(kind="issue", repo=repo, n=p["issue"]["number"], when=ev["created_at"]))
        elif kind == "WatchEvent":
            lines.append(dict(kind="star", repo=ev["repo"]["name"], when=ev["created_at"]))
        elif kind == "CreateEvent" and p.get("ref_type") == "repository":
            lines.append(dict(kind="create", repo=repo, when=ev["created_at"]))
        elif kind == "ReleaseEvent" and p.get("action") == "published":
            lines.append(dict(kind="release", repo=repo, tag=p["release"].get("tag_name", ""), when=ev["created_at"]))
        elif kind == "ForkEvent":
            lines.append(dict(kind="fork", repo=ev["repo"]["name"], when=ev["created_at"]))
    out = []
    for l in lines[:limit]:
        k = l["kind"]
        if k == "push":
            text = f"pushed {l['n']} commit{'s' if l['n'] != 1 else ''} to {l['repo']}"
        elif k == "pr":
            text = f"{l['verb']} PR #{l['n']} in {l['repo']}"
        elif k == "issue":
            text = f"opened issue #{l['n']} in {l['repo']}"
        elif k == "star":
            text = f"starred {l['repo']}"
        elif k == "create":
            text = f"created {l['repo']}"
        elif k == "release":
            text = f"released {l['tag']} in {l['repo']}"
        else:
            text = f"forked {l['repo']}"
        out.append((k, text, rel_time(l["when"], now)))
    return out


# ─────────────────────────────── renderers ───────────────────────────────
def svg_open(w, h, label):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}">'


def card_stats(t, d):
    W, H = FULL_W, 236
    c = d["contrib"]
    cal = c["contributionCalendar"]
    days = [(dt.date.fromisoformat(x["date"]), x["contributionCount"]) for w in cal["weeks"] for x in w["contributionDays"]]
    cur, longest, _ = streaks(days, d["today"])
    stars = sum(r["stargazers_count"] for r in d["own"])
    commits = c["totalCommitContributions"] + c["restrictedContributionsCount"]
    prs = c["totalPullRequestContributions"] + c["totalPullRequestReviewContributions"]
    langs = len([n for n in d["langs"] if n not in IGNORED_LANGS])
    tiles = [
        ("contributions", cal["totalContributions"], "past year", t["prompt"]),
        ("commits", commits, "past year", t["cmd"]),
        ("public repos", len(d["own"]), "original, not forks", t["text"]),
        ("stars earned", stars, "across repos", t["star"]),
        ("followers", d["user"]["followers"], "on github", t["pr"]),
        ("languages", langs, "in public code", t["accent2"]),
        ("current streak", cur, "days", t["warn"]),
        ("longest streak", longest, "days", t["issue"]),
    ]
    if prs:  # show PR work instead of the language count when there is any
        tiles[5] = ("pull requests", prs, "opened + reviewed", t["accent2"])
    out = [svg_open(W, H, f"GitHub stats for {LOGIN}"), window(t, "st", W, H, f"{LOGIN}@github: ~/stats", glow_pos=((W - 120, 30, 200), (80, H + 20, 170)))]
    s, now = prompt_line(t, "st", 28, 76, f"gh stats --user {LOGIN} --since 1y", 0.2, size=14)
    out.append(s)
    now += 0.2
    col_w = (W - 56) / 4
    for i, (label, val, sub, color) in enumerate(tiles):
        x = 28 + (i % 4) * col_w
        y = 118 + (i // 4) * 56
        tile = (f'<text x="{x}" y="{y}" font-family="{SANS}" font-size="26" font-weight="800" letter-spacing="-0.5" fill="{color}">{fmt(val)}</text>'
                f'<text x="{x}" y="{y + 16}" font-family="{MONO}" font-size="11" fill="{t["text"]}">{esc(label)}</text>'
                f'<text x="{x}" y="{y + 30}" font-family="{MONO}" font-size="10" fill="{t["muted"]}">{esc(sub)}</text>')
        out.append(fade(tile, round(now + i * 0.08, 2)))
    out.append(cursor(t, 28, H - 16, round(now + 0.8, 2), size=14))
    out.append('</svg>')
    return "\n".join(out)


def card_languages(t, d):
    W, H = HALF_W, 236
    total_all = sum(d["langs"].values()) or 1
    items = sorted(((n, b) for n, b in d["langs"].items() if n not in IGNORED_LANGS), key=lambda x: -x[1])[:6]
    total = sum(b for _, b in items) or 1
    out = [svg_open(W, H, f"Most used languages for {LOGIN}"), window(t, "lg", W, H, "~/languages", glow_pos=((W - 80, 30, 150), (40, H + 10, 130)))]
    s, now = prompt_line(t, "lg", 24, 72, "tokei --sort bytes", 0.2, size=13)
    out.append(s)
    now += 0.2
    # Stacked bar
    bx, by, bw, bh = 24, 88, W - 48, 10
    out.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="5" fill="{t["track"]}"/>')
    out.append(f'<clipPath id="lg-bar"><rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="5"/></clipPath><g clip-path="url(#lg-bar)">')
    x = bx
    for i, (n, b) in enumerate(items):
        w = bw * b / total
        out.append(f'<rect x="{x}" y="{by}" width="0" height="{bh}" fill="{d["colors"].get(n, "#8b949e")}"><animate attributeName="width" from="0" to="{w:.2f}" dur="0.6s" begin="{round(now + i*0.08, 2)}s" fill="freeze"/></rect>')
        x += w
    out.append('</g>')
    # Rows
    for i, (n, b) in enumerate(items):
        y = 122 + i * 19
        pct = 100 * b / total
        row = (f'<circle cx="30" cy="{y - 4}" r="4.5" fill="{d["colors"].get(n, "#8b949e")}"/>'
               f'<text x="42" y="{y}" font-family="{MONO}" font-size="12" fill="{t["text"]}">{esc(n)}</text>'
               f'<text x="{W - 24}" y="{y}" text-anchor="end" font-family="{MONO}" font-size="12" fill="{t["muted"]}">{pct:4.1f}%</text>'
               f'<text x="{W - 84}" y="{y}" text-anchor="end" font-family="{MONO}" font-size="10" fill="{t["faint"]}">{fmt(b // 1024)} kB</text>')
        out.append(fade(row, round(now + 0.3 + i * 0.1, 2)))
    if not items:
        out.append(fade(f'<text x="24" y="130" font-family="{MONO}" font-size="12" fill="{t["muted"]}">no public code yet</text>', now))
    out.append('</svg>')
    return "\n".join(out)


def card_activity(t, d):
    W, H = HALF_W, 236
    rows = summarize_events(d["events"], limit=6)
    glyph = {"push": ("↑", t["push"]), "pr": ("⎇", t["pr"]), "issue": ("◉", t["issue"]), "star": ("★", t["star"]),
             "create": ("+", t["create"]), "release": ("⬢", t["accent"]), "fork": ("⑂", t["muted"])}
    out = [svg_open(W, H, f"Recent public activity for {LOGIN}"), window(t, "ac", W, H, "~/activity", glow_pos=((W - 60, 40, 140), (60, H + 10, 130)))]
    s, now = prompt_line(t, "ac", 24, 72, "git reflog --public | head -6", 0.2, size=13)
    out.append(s)
    now += 0.2
    max_chars = 38
    for i, (k, text, when) in enumerate(rows):
        y = 100 + i * 21
        g, col = glyph[k]
        if len(text) > max_chars:
            text = text[:max_chars - 1] + "…"
        row = (f'<text x="26" y="{y}" font-family="{MONO}" font-size="13" fill="{col}" font-weight="700">{esc(g)}</text>'
               f'<text x="44" y="{y}" font-family="{MONO}" font-size="12" fill="{t["text"]}">{esc(text)}</text>'
               f'<text x="{W - 24}" y="{y}" text-anchor="end" font-family="{MONO}" font-size="10" fill="{t["muted"]}">{esc(when)}</text>')
        out.append(fade(row, round(now + i * 0.12, 2)))
    if not rows:
        out.append(fade(f'<text x="26" y="100" font-family="{MONO}" font-size="12" fill="{t["muted"]}">quiet lately… probably shipping in private</text>', now))
    out.append(cursor(t, 24, H - 16, round(now + 0.9, 2), size=13))
    out.append('</svg>')
    return "\n".join(out)


def card_calendar(t, d):
    W, H = FULL_W, 252
    cal = d["contrib"]["contributionCalendar"]
    weeks = cal["weeks"]
    days = [(dt.date.fromisoformat(x["date"]), x["contributionCount"]) for w in weeks for x in w["contributionDays"]]
    cur, longest, busiest = streaks(days, d["today"])
    level = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
    out = [svg_open(W, H, f"Contribution calendar for {LOGIN}"), window(t, "cl", W, H, "~/contributions", glow_pos=((W - 100, 20, 200), (100, H + 30, 170)))]
    s, now = prompt_line(t, "cl", 28, 72, "git log --since 1y | heatmap", 0.2, size=14)
    out.append(s)
    now += 0.1
    cell, gap = 12, 3
    ncols = len(weeks)
    gx = 28 + 30
    gw = ncols * (cell + gap) - gap
    scale = min(1.0, (W - gx - 28) / gw)
    gy = 104
    out.append(f'<g transform="translate({gx} {gy}) scale({scale:.4f})">')
    # weekday labels
    for r, lab in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="-8" y="{r*(cell+gap)+cell-2}" text-anchor="end" font-family="{MONO}" font-size="10" fill="{t["muted"]}">{lab}</text>')
    # month labels
    for c, w in enumerate(weeks):
        days_in_week = [dt.date.fromisoformat(x["date"]) for x in w["contributionDays"]]
        # label the week that contains the 1st of a month (skip if it would overflow)
        if any(x.day == 1 for x in days_in_week) and c * (cell + gap) + 26 < gw:
            m = next(x for x in days_in_week if x.day == 1)
            out.append(f'<text x="{c*(cell+gap)}" y="-6" font-family="{MONO}" font-size="10" fill="{t["muted"]}">{m.strftime("%b")}</text>')
    for c, w in enumerate(weeks):
        for x in w["contributionDays"]:
            r = dt.date.fromisoformat(x["date"]).weekday()
            r = (r + 1) % 7  # Sunday first, like GitHub
            lv = level.get(x["contributionLevel"], 0)
            px, py = c * (cell + gap), r * (cell + gap)
            out.append(f'<rect x="{px}" y="{py}" width="{cell}" height="{cell}" rx="2.5" fill="{t["cell"]}" stroke="{t["cell_border"]}" stroke-width="0.5"/>')
            if lv:
                delay = round(now + c * 0.022, 3)
                out.append(f'<rect x="{px}" y="{py}" width="{cell}" height="{cell}" rx="2.5" fill="{t["levels"][lv-1]}" opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.4s" begin="{delay}s" fill="freeze"/></rect>')
    out.append('</g>')
    # summary line
    sy = gy + 7 * (cell + gap) * scale + 22
    busiest_txt = f"{busiest[0].strftime('%b %-d')} ({busiest[1]})" if busiest[0] else "—"
    parts = [("total", fmt(cal["totalContributions"]), t["prompt"]), ("current streak", f"{cur}d", t["warn"]),
             ("longest streak", f"{longest}d", t["issue"]), ("busiest day", busiest_txt, t["cmd"])]
    x = 28
    line = []
    for lab, val, col in parts:
        line.append(f'<text x="{x}" y="{sy}" font-family="{MONO}" font-size="12"><tspan fill="{t["muted"]}">{lab} </tspan><tspan fill="{col}" font-weight="700">{esc(val)}</tspan></text>')
        x += 7.3 * (len(lab) + len(val) + 1) + 26
    out.append(fade("".join(line), round(now + ncols * 0.022 + 0.2, 2)))
    lx = W - 28 - 4 * 14 - 62
    out.append(f'<g font-family="{MONO}" font-size="10" fill="{t["muted"]}"><text x="{lx}" y="{sy}">less</text>')
    for i, lv in enumerate(t["levels"]):
        out.append(f'<rect x="{lx + 30 + i*14}" y="{sy - 9}" width="10" height="10" rx="2" fill="{lv}"/>')
    out.append(f'<text x="{lx + 30 + 4*14 + 4}" y="{sy}">more</text></g>')
    out.append('</svg>')
    return "\n".join(out)


CARDS = {"stats": card_stats, "languages": card_languages, "activity": card_activity, "calendar": card_calendar}


def main():
    d = fetch()
    print(f"fetched: {len(d['own'])} own repos, {len(d['langs'])} languages, {len(d['events'])} events, "
          f"{d['contrib']['contributionCalendar']['totalContributions']} contributions")
    for name, fn in CARDS.items():
        for theme, t in THEMES.items():
            p = OUT / f"{name}-{theme}.svg"
            p.write_text(fn(t, d))
            print(f"wrote {p.relative_to(OUT.parent)} ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
