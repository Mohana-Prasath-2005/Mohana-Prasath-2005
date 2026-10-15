import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

USER = os.environ.get("GH_USER", "Mohana-Prasath-2005")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = sys.argv[1] if len(sys.argv) > 1 else "assets/activity-card.svg"

def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(body["errors"])
    return body["data"]


CAL = """
query($login: String!, $from: DateTime, $to: DateTime) {
  user(login: $login) {
    createdAt
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
  }
}
"""


def fetch():
    now = datetime.now(timezone.utc)
    created = datetime.fromisoformat(gql(CAL, {"login": USER})["user"]["createdAt"].replace("Z", "+00:00"))
    days, recent = {}, None
    start = created
    while start < now:
        end = min(start + timedelta(days=365), now)
        cal = gql(CAL, {"login": USER, "from": start.isoformat(), "to": end.isoformat()})
        weeks = cal["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        for w in weeks:
            for d in w["contributionDays"]:
                if d["date"] not in days or d["contributionCount"] > days[d["date"]]["contributionCount"]:
                    days[d["date"]] = d
        start = end
    recent = gql(CAL, {"login": USER})["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return created.date(), days, recent


def streaks(days, today):
    counts = {date.fromisoformat(k): v["contributionCount"] for k, v in days.items()}
    cur_end = today if counts.get(today, 0) > 0 else today - timedelta(days=1)
    d, cur = cur_end, 0
    while counts.get(d, 0) > 0:
        cur += 1
        d -= timedelta(days=1)
    cur_start = cur_end - timedelta(days=cur - 1)

    best, best_range, run, run_start = 0, None, 0, None
    for day in sorted(counts):
        if counts[day] > 0:
            run_start = day if run == 0 else run_start
            run += 1
            if run > best:
                best, best_range = run, (run_start, day)
        else:
            run = 0
    return cur, (cur_start, cur_end), best, best_range


def fmt(d):
    return d.strftime("%b %-d")


def smooth(pts, floor):
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0, p1 = pts[max(i - 1, 0)], pts[i]
        p2, p3 = pts[i + 1], pts[min(i + 2, len(pts) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, min(p1[1] + (p2[1] - p0[1]) / 6, floor))
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, min(p2[1] - (p3[1] - p1[1]) / 6, floor))
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d


def render(created, days, recent):
    today = datetime.now(timezone.utc).date()
    total = sum(v["contributionCount"] for v in days.values())
    cur, cur_range, best, best_range = streaks(days, today)

    weeks = [(date.fromisoformat(w["contributionDays"][0]["date"]), sum(d["contributionCount"] for d in w["contributionDays"])) for w in recent]
    year_total = sum(v for _, v in weeks)
    peak_i = max(range(len(weeks)), key=lambda i: weeks[i][1])

    W, H = 900, 384
    cx0, cx1, top, base = 40, 860, 240, 334
    vmax = max(v for _, v in weeks) or 1
    step = (cx1 - cx0) / (len(weeks) - 1)
    pts = [(cx0 + i * step, base - (v / vmax) * (base - top)) for i, (_, v) in enumerate(weeks)]
    line = smooth(pts, base)
    area = f"{line} L{cx1},{base} L{cx0},{base} Z"
    px, py = pts[peak_i]
    lx, ly = pts[-1]

    months, seen = [], set()
    for i, (d, _) in enumerate(weeks):
        if d.day <= 7 and (d.year, d.month) not in seen and 0 < i < len(weeks) - 2:
            seen.add((d.year, d.month))
            months.append(f'<text class="m" x="{cx0 + i * step:.1f}" y="{base + 22}" text-anchor="middle">{d.strftime("%b")}</text>')

    cur_sub = f"{fmt(cur_range[0])} – {fmt(cur_range[1])}" if cur else "start one today"
    best_sub = f"{fmt(best_range[0])} – {fmt(best_range[1])}, {best_range[1].year}" if best_range else "—"
    peak_lbl_x = min(max(px, cx0 + 60), cx1 - 60)

    def stat(x, num, color, label, sub, delay, extra=""):
        return f"""
  <g class="in" style="animation-delay:{delay}s">
    <text class="num" x="{x}" y="118" text-anchor="middle" fill="{color}">{num}</text>
    <text class="lbl" x="{x}" y="146" text-anchor="middle">{label}</text>
    <text class="sub" x="{x}" y="166" text-anchor="middle">{sub}</text>{extra}
  </g>"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" fill="none">
  <defs>
    <linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#b48cff"/><stop offset="1" stop-color="#00BFFF"/></linearGradient>
    <linearGradient id="stroke" x1="0" x2="1"><stop offset="0" stop-color="#8A2BE2"/><stop offset=".6" stop-color="#7a5cff"/><stop offset="1" stop-color="#00BFFF"/></linearGradient>
    <linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8A2BE2" stop-opacity=".28"/><stop offset="1" stop-color="#8A2BE2" stop-opacity="0"/></linearGradient>
    <linearGradient id="fire" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#00BFFF"/><stop offset="1" stop-color="#b48cff"/></linearGradient>
    <filter id="glow" x="-10%" y="-50%" width="120%" height="200%"><feGaussianBlur stdDeviation="4"/></filter>
  </defs>
  <style>
    text {{ font-family: 'JetBrains Mono', 'SFMono-Regular', Menlo, Consolas, monospace; }}
    .t {{ fill: #6e7681; font-size: 11px; letter-spacing: .5px; }}
    .num {{ font-size: 46px; font-weight: 800; letter-spacing: -1px; }}
    .lbl {{ fill: #8b949e; font-size: 10.5px; letter-spacing: 2.2px; }}
    .sub {{ fill: #484f58; font-size: 11px; }}
    .m {{ fill: #484f58; font-size: 10px; }}
    .cap {{ fill: #6e7681; font-size: 10px; letter-spacing: 2px; }}
    .pk {{ fill: #e6edf3; font-size: 10.5px; }}
    .in {{ opacity: 0; animation: rise .7s ease-out forwards; }}
    @keyframes rise {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}
    .draw {{ stroke-dasharray: 1; stroke-dashoffset: 1; animation: draw 2.4s cubic-bezier(.4,0,.2,1) .5s forwards; }}
    @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
    .fade {{ opacity: 0; animation: rise 1.2s ease-out 1.6s forwards; }}
    .ping {{ transform-origin: {lx:.1f}px {ly:.1f}px; animation: ping 2s ease-out 2.9s infinite; opacity: 0; }}
    @keyframes ping {{ 0% {{ opacity: .8; transform: scale(1); }} 100% {{ opacity: 0; transform: scale(3.2); }} }}
    .flame {{ animation: flick 1.4s ease-in-out infinite; }}
    @keyframes flick {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: .5; }} }}
  </style>

  <rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="#0d1117" stroke="#21262d"/>
  <circle cx="22" cy="20" r="5.5" fill="#ff5f57"/><circle cx="40" cy="20" r="5.5" fill="#febc2e"/><circle cx="58" cy="20" r="5.5" fill="#28c840"/>
  <text class="t" x="{W / 2}" y="24" text-anchor="middle">~/activity</text>
  <text class="t" x="{W - 22}" y="24" text-anchor="end" style="fill:#3fb950">● synced {today.strftime('%b %-d')}</text>

  {stat(170, f"{total:,}", "url(#g)", "CONTRIBUTIONS", f"since {created.strftime('%b %Y')}", .1)}
  <line x1="320" y1="84" x2="320" y2="170" stroke="#21262d"/>
  {stat(450, cur, "#e6edf3", "CURRENT STREAK", cur_sub, .25, f'<path class="flame" transform="translate({450 + 20 + 14 * len(str(cur))},86)" d="M0,-10 C5,-4 7,0 7,4 A7,7 0 0 1 -7,4 C-7,0 -4,-2 -3,-6 C-2,-3 -1,-2 0,-2 C1,-5 1,-7 0,-10 Z" fill="url(#fire)"/>')}
  <line x1="580" y1="84" x2="580" y2="170" stroke="#21262d"/>
  {stat(730, best, "#f2cc60", "LONGEST STREAK", best_sub, .4)}

  <text class="cap" x="{cx0}" y="206">LAST 12 MONTHS</text>
  <text class="cap" x="{cx1}" y="206" text-anchor="end">{year_total:,} CONTRIBUTIONS</text>
  <line x1="{cx0}" y1="{base}" x2="{cx1}" y2="{base}" stroke="#21262d"/>

  <path class="fade" d="{area}" fill="url(#area)"/>
  <path class="draw" d="{line}" pathLength="1" stroke="url(#stroke)" stroke-width="6" stroke-linecap="round" opacity=".35" filter="url(#glow)"/>
  <path class="draw" d="{line}" pathLength="1" stroke="url(#stroke)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>

  <g class="fade">
    <line x1="{px:.1f}" y1="{py:.1f}" x2="{px:.1f}" y2="{base}" stroke="#30363d" stroke-dasharray="2 3"/>
    <circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="#0d1117" stroke="#b48cff" stroke-width="2"/>
    <text class="pk" x="{peak_lbl_x:.1f}" y="{py - 12:.1f}" text-anchor="middle">peak · {weeks[peak_i][1]} in a week</text>
    <circle class="ping" cx="{lx:.1f}" cy="{ly:.1f}" r="4" fill="#00BFFF"/>
    <circle cx="{lx:.1f}" cy="{ly:.1f}" r="4" fill="#00BFFF"/>
  </g>
  {''.join(months)}
</svg>
"""


if __name__ == "__main__":
    created, days, recent = fetch()
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w") as f:
        f.write(render(created, days, recent))
    print(f"wrote {OUT}")
