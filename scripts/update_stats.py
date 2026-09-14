"""Fetch GitHub account metrics and rewrite the generated parts of the profile.

- README.md: replaces the blocks between <!-- NAME:START --> and <!-- NAME:END -->
  (STATS, HEALTH).
- assets/activity-{dark,light}.svg: contribution heatmap rendered from the calendar.

Needs a token in GH_TOKEN that can read the user's private repositories.
"""

import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

USERNAME = os.environ.get("GH_USER", "Yeshush")
ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
ASSETS = ROOT / "assets"
BAR_WIDTH = 48
TOP_LANGUAGES = 6
# Build/config languages that would distort the "what do I code in" picture.
IGNORED_LANGUAGES = {"Makefile", "Dockerfile", "Batchfile", "Shell"}
# Without a contribution for this long the health status flips to OUT_OF_SERVICE.
IDLE_AFTER = timedelta(days=14)

WEEKDAYS = ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"]
MONTHS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]

# Spring-green heatmap palettes: empty cell, levels 1-4, label text.
THEMES = {
    "dark": {"empty": "#1b222c", "levels": ["#203b16", "#38652a", "#52943a", "#7cc84d"], "text": "#8b949e"},
    "light": {"empty": "#ebedf0", "levels": ["#d4ebc4", "#a6d485", "#6db33f", "#3f7a1f"], "text": "#57606a"},
}


def graphql(query: str, token: str) -> dict:
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


def fetch_metrics(token: str, now: datetime) -> dict:
    years = [now.year - 2, now.year - 1, now.year]
    year_fields = "\n".join(
        f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z")'
        " { contributionCalendar { totalContributions } }"
        for y in years
    )
    data = graphql(
        f"""{{
          user(login: "{USERNAME}") {{
            lastYear: contributionsCollection {{
              contributionCalendar {{
                totalContributions
                weeks {{ contributionDays {{ date weekday contributionCount }} }}
              }}
            }}
            {year_fields}
            all: repositories(ownerAffiliations: OWNER) {{ totalCount }}
            public: repositories(ownerAffiliations: OWNER, privacy: PUBLIC) {{ totalCount }}
            owned: repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {{
              nodes {{ languages(first: 20) {{ edges {{ size node {{ name }} }} }} }}
            }}
          }}
        }}""",
        token,
    )["user"]

    languages: dict[str, int] = {}
    for repo in data["owned"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name not in IGNORED_LANGUAGES:
                languages[name] = languages.get(name, 0) + edge["size"]

    calendar = data["lastYear"]["contributionCalendar"]
    return {
        "last_year": calendar["totalContributions"],
        "weeks": [week["contributionDays"] for week in calendar["weeks"]],
        "per_year": {y: data[f"y{y}"]["contributionCalendar"]["totalContributions"] for y in years},
        "repos_total": data["all"]["totalCount"],
        "repos_public": data["public"]["totalCount"],
        "languages": languages,
    }


def swiss(number: int) -> str:
    return f"{number:,}".replace(",", "'")


def language_chart(languages: dict[str, int]) -> str:
    total = sum(languages.values()) or 1
    ranked = sorted(languages.items(), key=lambda item: item[1], reverse=True)
    rows = ranked[:TOP_LANGUAGES]
    rest = sum(size for _, size in ranked[TOP_LANGUAGES:])
    if rest:
        rows.append(("Andere", rest))

    lines = []
    for name, size in rows:
        share = size / total
        filled = round(share * BAR_WIDTH)
        bar = "█" * filled + "░" * (BAR_WIDTH - filled)
        lines.append(f"{name:<12} {bar}  {share * 100:4.1f} %")
    return "\n".join(lines)


def render_stats(metrics: dict, now: datetime) -> str:
    years = sorted(metrics["per_year"])
    trend = " → ".join(swiss(metrics["per_year"][y]) for y in years)
    return f"""| Contributions (12 Monate) | Repositories | Contributions {" → ".join(map(str, years))}* |
|:---:|:---:|:---:|
| **{swiss(metrics["last_year"])}** | **{metrics["repos_total"]}** ({metrics["repos_public"]} öffentlich) | **{trend}** |

```text
{language_chart(metrics["languages"])}
```

<sub>Inkl. privater Repositories · Sprachen nach Codemenge · * {years[-1]} bis heute · automatisch aktualisiert am {now:%d.%m.%Y}</sub>"""


def activity_insights(days: list[dict], today: date) -> dict:
    """Derive streaks and habits from the flat list of calendar days (oldest first)."""
    days = [d for d in days if date.fromisoformat(d["date"]) <= today]
    active = [d for d in days if d["contributionCount"] > 0]

    longest = run = 0
    for day in days:
        run = run + 1 if day["contributionCount"] > 0 else 0
        longest = max(longest, run)

    # Today may simply not have started yet, so a streak ending yesterday still counts.
    current = 0
    tail = days[:-1] if days and days[-1]["contributionCount"] == 0 else days
    for day in reversed(tail):
        if day["contributionCount"] == 0:
            break
        current += 1

    per_weekday = [0] * 7
    for day in days:
        per_weekday[day["weekday"]] += day["contributionCount"]

    best = max(days, key=lambda d: d["contributionCount"], default=None)
    last = date.fromisoformat(active[-1]["date"]) if active else None
    return {
        "status": "UP" if last and today - last <= IDLE_AFTER else "OUT_OF_SERVICE",
        "lastContribution": last.isoformat() if last else None,
        "currentStreakDays": current,
        "longestStreakDays": longest,
        "activeDays": f"{len(active)} / {len(days)}",
        "busiestWeekday": WEEKDAYS[per_weekday.index(max(per_weekday))],
        "bestDay": f"{best['date']} ({best['contributionCount']} Contributions)" if best else None,
    }


def render_health(insights: dict) -> str:
    body = {
        "status": insights["status"],
        "components": {
            "backend": {"status": "UP", "details": {"stack": "Java · Spring Boot"}},
            "frontend": {"status": "UP", "details": {"stack": "Angular · TypeScript"}},
            "activity": {
                "status": insights["status"],
                "details": {k: v for k, v in insights.items() if k != "status"},
            },
        },
    }
    return f"""```http
GET /actuator/health HTTP/1.1
Host: github.com/{USERNAME}
```

```json
{json.dumps(body, indent=2, ensure_ascii=False)}
```"""


def render_heatmap(weeks: list[list[dict]], total: int, theme: dict) -> str:
    cell, step, left, top = 10, 13, 30, 20
    width = left + len(weeks) * step + 10
    height = top + 7 * step + 28

    counts = sorted(d["contributionCount"] for week in weeks for d in week if d["contributionCount"] > 0)
    # Quartiles of non-zero days, so one extreme day doesn't wash out the rest.
    thresholds = [counts[len(counts) * q // 4] for q in (1, 2, 3)] if counts else [1, 1, 1]

    def color(count: int) -> str:
        if count == 0:
            return theme["empty"]
        return theme["levels"][sum(count > t for t in thresholds)]

    font = 'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="10"'
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<g fill="{theme["text"]}" {font}>',
    ]

    last_label_week = -10
    for index, week in enumerate(weeks):
        month = date.fromisoformat(week[0]["date"]).month
        previous = date.fromisoformat(weeks[index - 1][0]["date"]).month if index else None
        if month != previous and index - last_label_week >= 3:
            parts.append(f'<text x="{left + index * step}" y="{top - 7}">{MONTHS[month - 1]}</text>')
            last_label_week = index
    for row, label in ((1, "Mo"), (3, "Mi"), (5, "Fr")):
        parts.append(f'<text x="0" y="{top + row * step + 9}">{label}</text>')
    parts.append("</g>")

    for index, week in enumerate(weeks):
        for day in week:
            x, y = left + index * step, top + day["weekday"] * step
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{color(day["contributionCount"])}"/>'
            )

    legend_y = top + 7 * step + 10
    parts.append(
        f'<text x="{left}" y="{legend_y + 9}" fill="{theme["text"]}" {font}>'
        f"{swiss(total)} Contributions in den letzten 12 Monaten</text>"
    )
    legend_x = width - 10 - 5 * step - 66
    parts.append(f'<text x="{legend_x}" y="{legend_y + 9}" fill="{theme["text"]}" {font}>Weniger</text>')
    for i, fill in enumerate([theme["empty"], *theme["levels"]]):
        parts.append(
            f'<rect x="{legend_x + 42 + i * step}" y="{legend_y}" width="{cell}" height="{cell}" rx="2" fill="{fill}"/>'
        )
    parts.append(
        f'<text x="{legend_x + 42 + 5 * step + 2}" y="{legend_y + 9}" fill="{theme["text"]}" {font}>Mehr</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def replace_block(readme: str, name: str, content: str) -> str:
    start, end = f"<!-- {name}:START -->", f"<!-- {name}:END -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(readme):
        raise ValueError(f"Markers {start} / {end} not found in README.md")
    return pattern.sub(lambda _: f"{start}\n{content}\n{end}", readme)


def main() -> int:
    token = os.environ.get("GH_TOKEN")
    if not token:
        print("GH_TOKEN is not set", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    metrics = fetch_metrics(token, now)
    days = [day for week in metrics["weeks"] for day in week]

    readme = README.read_text(encoding="utf-8")
    try:
        readme = replace_block(readme, "STATS", render_stats(metrics, now))
        readme = replace_block(readme, "HEALTH", render_health(activity_insights(days, now.date())))
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    README.write_text(readme, encoding="utf-8")

    ASSETS.mkdir(exist_ok=True)
    for name, theme in THEMES.items():
        svg = render_heatmap(metrics["weeks"], metrics["last_year"], theme)
        (ASSETS / f"activity-{name}.svg").write_text(svg, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
