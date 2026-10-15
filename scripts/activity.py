import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html import escape

USER = os.environ.get("GH_USER", "Mohana-Prasath-2005")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = sys.argv[1] if len(sys.argv) > 1 else "assets/activity.svg"

LEVELS = {
    "NONE": "#161b22",
    "FIRST_QUARTILE": "#3b1d6e",
    "SECOND_QUARTILE": "#6a2bc2",
    "THIRD_QUARTILE": "#8A2BE2",
    "FOURTH_QUARTILE": "#00BFFF",
}


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


def render(created, days, recent):
    today = datetime.now(timezone.utc).date()
    total = sum(v["contributionCount"] for v in days.values())
    cur, cur_range, best, best_range = streaks(days, today)

    year_days = [d for w in recent for d in w["contributionDays"]]
    year_total = sum(d["contributionCount"] for d in year_days)
    active = sum(1 for d in year_days if d["contributionCount"] > 0)
    peak = max(year_days, key=lambda d: d["contributionCount"])
    peak_date = date.fromisoformat(peak["date"])

    W, H = 900, 350
    x0, y0, cell, gap = 54, 200, 12, 3
    pitch = cell + gap

    cells, months, last_month = [], [], None
    for wi, w in enumerate(recent):
        for d in w["contributionDays"]:
            dt = date.fromisoformat(d["date"])
            row = (dt.weekday() + 1) % 7
            x, y = x0 + wi * pitch, y0 + row * pitch
            fill = LEVELS[d["contributionLevel"]]
            delay = wi * 0.025
            cells.append(
                f'<rect class="c" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" fill="{fill}" '
                f'style="animation-delay:{delay:.3f}s"><title>{d["contributionCount"]} on {d["date"]}</title></rect>'
            )
            if row == 0 and dt.month != last_month and dt.day <= 7:
                months.append(f'<text class="m" x="{x}" y="{y0 - 8}">{dt.strftime("%b")}</text>')
                last_month = dt.month
    grid_w = len(recent) * pitch - gap

    pct = 0 if best == 0 else min(cur / best, 1)
    bar_w = 236
    cur_sub = f"{fmt(cur_range[0])} – {fmt(cur_range[1])}" if cur else "start one today"
    best_sub = f"{fmt(best_range[0])} – {fmt(best_range[1])}, {best_range[1].year}" if best_range else "—"

    legend = "".join(
        f'<rect x="{W - 22 - 150 + 34 + i * 15}" y="{H - 30}" width="11" height="11" rx="2.5" fill="{c}"/>'
        for i, c in enumerate(LEVELS.values())
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" fill="none">
  <defs>
    <linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#b48cff"/><stop offset="1" stop-color="#00BFFF"/></linearGradient>
    <linearGradient id="bar" x1="0" x2="1"><stop offset="0" stop-color="#8A2BE2"/><stop offset="1" stop-color="#00BFFF"/></linearGradient>
    <linearGradient id="scan" x1="0" x2="1">
      <stop offset="0" stop-color="#00BFFF" stop-opacity="0"/>
      <stop offset="0.5" stop-color="#00BFFF" stop-opacity="0.22"/>
      <stop offset="1" stop-color="#00BFFF" stop-opacity="0"/>
    </linearGradient>
    <clipPath id="gridclip"><rect x="{x0 - 4}" y="{y0 - 4}" width="{grid_w + 8}" height="{7 * pitch + 5}"/></clipPath>
  </defs>
  <style>
    text {{ font-family: 'JetBrains Mono', 'SFMono-Regular', Menlo, Consolas, monospace; }}
    .t {{ fill: #6e7681; font-size: 11px; letter-spacing: .5px; }}
    .p {{ fill: #8A2BE2; font-size: 13px; }}
    .cmd {{ fill: #00BFFF; font-size: 13px; }}
    .lbl {{ fill: #6e7681; font-size: 10px; letter-spacing: 1.4px; }}
    .num {{ font-size: 34px; font-weight: 800; }}
    .unit {{ fill: #8b949e; font-size: 12px; }}
    .sub {{ fill: #8b949e; font-size: 11px; }}
    .m, .d {{ fill: #6e7681; font-size: 10px; }}
    .f {{ fill: #8b949e; font-size: 11px; }}
    .hl {{ fill: #e6edf3; font-weight: 700; }}
    .c {{ opacity: 0; animation: pop .5s ease-out forwards; }}
    @keyframes pop {{ from {{ opacity: 0; transform: translateY(3px); }} to {{ opacity: 1; transform: none; }} }}
    .tile {{ opacity: 0; animation: pop .6s ease-out forwards; }}
    .flame {{ transform-origin: 0 0; animation: flick 1.4s ease-in-out infinite; }}
    @keyframes flick {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: .55; }} }}
    .fill {{ animation: grow 1.6s cubic-bezier(.2,.8,.2,1) .6s both; transform-origin: left; transform-box: fill-box; }}
    @keyframes grow {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
    .scan {{ animation: sweep 5s linear 1.8s infinite; }}
    @keyframes sweep {{ from {{ transform: translateX(-80px); }} to {{ transform: translateX({grid_w + 80}px); }} }}
    .live {{ animation: flick 1.6s ease-in-out infinite; }}
  </style>

  <rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="#0d1117" stroke="#21262d"/>
  <path d="M1 36 V12.5 A12 12 0 0 1 13 .5 H{W - 13} A12 12 0 0 1 {W - 1} 12.5 V36 Z" fill="#11151c"/>
  <line x1="1" y1="36" x2="{W - 1}" y2="36" stroke="#21262d"/>
  <circle cx="22" cy="18" r="6" fill="#ff5f57"/><circle cx="42" cy="18" r="6" fill="#febc2e"/><circle cx="62" cy="18" r="6" fill="#28c840"/>
  <text class="t" x="82" y="22">mohan@github ~ /activity</text>
  <circle class="live" cx="{W - 120}" cy="18" r="3.5" fill="#3fb950"/>
  <text class="t" x="{W - 110}" y="22" style="fill:#3fb950">synced {today.strftime('%b %-d')}</text>

  <text x="22" y="64"><tspan class="p">❯ </tspan><tspan class="cmd">git log --author=mohana --since={created.isoformat()} --stat</tspan></text>

  <g class="tile" style="animation-delay:.1s">
    <rect x="22" y="80" width="272" height="88" rx="8" fill="#11151c" stroke="#21262d"/>
    <rect x="22" y="80" width="3" height="88" rx="1.5" fill="#8A2BE2"/>
    <text class="lbl" x="40" y="101">TOTAL CONTRIBUTIONS</text>
    <text x="40" y="141"><tspan class="num" fill="url(#g)">{total:,}</tspan><tspan class="unit" dx="8">commits · PRs · reviews</tspan></text>
    <text class="sub" x="40" y="158">since {created.strftime('%b %-d, %Y')}</text>
  </g>

  <g class="tile" style="animation-delay:.25s">
    <rect x="314" y="80" width="272" height="88" rx="8" fill="#11151c" stroke="#21262d"/>
    <rect x="314" y="80" width="3" height="88" rx="1.5" fill="#00BFFF"/>
    <text class="lbl" x="332" y="101">CURRENT STREAK</text>
    <text class="flame" x="540" y="104" font-size="16">🔥</text>
    <text x="332" y="135"><tspan class="num" fill="#e6edf3">{cur}</tspan><tspan class="unit" dx="8">day{'s' if cur != 1 else ''}</tspan></text>
    <rect x="332" y="143" width="{bar_w}" height="4" rx="2" fill="#21262d"/>
    <rect class="fill" x="332" y="143" width="{max(bar_w * pct, 4):.1f}" height="4" rx="2" fill="url(#bar)"/>
    <text class="sub" x="332" y="160">{cur_sub}</text>
    <text class="sub" x="{332 + bar_w}" y="160" text-anchor="end">{int(pct * 100)}% of best</text>
  </g>

  <g class="tile" style="animation-delay:.4s">
    <rect x="606" y="80" width="272" height="88" rx="8" fill="#11151c" stroke="#21262d"/>
    <rect x="606" y="80" width="3" height="88" rx="1.5" fill="#f2cc60"/>
    <text class="lbl" x="624" y="101">LONGEST STREAK</text>
    <text x="624" y="141"><tspan class="num" fill="#f2cc60">{best}</tspan><tspan class="unit" dx="8">days</tspan></text>
    <text class="sub" x="624" y="158">{best_sub}</text>
  </g>

  {''.join(months)}
  <text class="d" x="22" y="{y0 + 1 * pitch + 10}">Mon</text>
  <text class="d" x="22" y="{y0 + 3 * pitch + 10}">Wed</text>
  <text class="d" x="22" y="{y0 + 5 * pitch + 10}">Fri</text>
  {''.join(cells)}
  <g clip-path="url(#gridclip)"><rect class="scan" x="{x0 - 80}" y="{y0 - 4}" width="80" height="{7 * pitch + 5}" fill="url(#scan)"/></g>

  <text class="f" x="22" y="{H - 21}"><tspan class="hl">{year_total:,}</tspan> in the last year  ·  <tspan class="hl">{active}</tspan> active days  ·  peak <tspan class="hl">{peak['contributionCount']}</tspan> on {fmt(peak_date)}</text>
  <text class="m" x="{W - 22 - 150}" y="{H - 21}">less</text>
  {legend}
  <text class="m" x="{W - 22 - 150 + 34 + 5 * 15 + 4}" y="{H - 21}">more</text>
</svg>
"""


if __name__ == "__main__":
    created, days, recent = fetch()
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w") as f:
        f.write(render(created, days, recent))
    print(f"wrote {OUT}")
