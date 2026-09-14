"""Fetch GitHub account metrics and rewrite the generated parts of the profile.

For every language in LANGS:
- the README gets the blocks between <!-- NAME:START --> and <!-- NAME:END -->
  replaced (HEALTH, STATS, RHYTHM, CHANGELOG),
- assets/ gets a contribution heatmap and a monthly trend chart per theme.

Only aggregates are published: no repository names, so private and customer
repositories stay confidential.

Needs a token in GH_TOKEN that can read the user's private repositories.
"""

import json
import os
import re
import sys
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

USERNAME = os.environ.get("GH_USER", "Yeshush")
TIMEZONE = ZoneInfo(os.environ.get("GH_TZ", "Europe/Zurich"))
ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
BAR_WIDTH = 48
RHYTHM_BAR_WIDTH = 30
TOP_LANGUAGES = 6
CHANGELOG_MONTHS = 6
TREND_MONTHS = 12
# Build/config languages that would distort the "what do I code in" picture.
IGNORED_LANGUAGES = {"Makefile", "Dockerfile", "Batchfile", "Shell"}
# Without a contribution for this long the health status flips to OUT_OF_SERVICE.
IDLE_AFTER = timedelta(days=14)

LANGS = {
    "de": {
        "readme": "README.md",
        "suffix": "",
        "thousands": "'",
        "date": "%d.%m.%Y",
        "weekdays": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
        "months": ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
        "weekday_rows": ("Mo", "Mi", "Fr"),
        "stats_header": "| Contributions (12 Monate) | Repositories | Contributions {years}* |",
        "public": "öffentlich",
        "stats_note": "Inkl. privater Repositories · Sprachen nach Codemenge · * {year} bis heute"
        " · automatisch aktualisiert am {date}",
        "others": "Andere",
        "best_day": "{date} ({n} Contributions)",
        "heatmap_total": "{n} Contributions in den letzten 12 Monaten",
        "less": "Weniger",
        "more": "Mehr",
        "trend_title": "Contributions pro Monat",
        "rhythm_title": "{n} Commits · letzte 12 Monate · Zeitzone {tz}",
        "slots": ["Nacht", "Morgen", "Nachmittag", "Abend"],
        "workdays": "Werktage",
        "weekend": "Wochenende",
        "peak_hour": "Peak-Stunde",
        "no_commits": "Noch keine Commits im Zeitraum gefunden.",
        "changelog_row": "Contributions {n} · aktive Tage {d}",
        "ongoing": "  (laufend)",
    },
    "en": {
        "readme": "README.en.md",
        "suffix": ".en",
        "thousands": ",",
        "date": "%Y-%m-%d",
        "weekdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "weekday_rows": ("Mon", "Wed", "Fri"),
        "stats_header": "| Contributions (12 months) | Repositories | Contributions {years}* |",
        "public": "public",
        "stats_note": "Including private repositories · languages by code size · * {year} to date"
        " · updated automatically on {date}",
        "others": "Other",
        "best_day": "{date} ({n} contributions)",
        "heatmap_total": "{n} contributions in the last 12 months",
        "less": "Less",
        "more": "More",
        "trend_title": "Contributions per month",
        "rhythm_title": "{n} commits · last 12 months · time zone {tz}",
        "slots": ["Night", "Morning", "Afternoon", "Evening"],
        "workdays": "Weekdays",
        "weekend": "Weekend",
        "peak_hour": "Peak hour",
        "no_commits": "No commits found in this period yet.",
        "changelog_row": "contributions {n} · active days {d}",
        "ongoing": "  (in progress)",
    },
}

# Spring-green palettes: empty cell, heatmap levels 1-4, trend line, label text.
THEMES = {
    "dark": {
        "empty": "#1b222c",
        "levels": ["#203b16", "#38652a", "#52943a", "#7cc84d"],
        "line": "#7cc84d",
        "text": "#8b949e",
    },
    "light": {
        "empty": "#ebedf0",
        "levels": ["#d4ebc4", "#a6d485", "#6db33f", "#3f7a1f"],
        "line": "#3f7a1f",
        "text": "#57606a",
    },
}
FONT = 'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="10"'


def graphql(query: str, token: str, variables: dict | None = None) -> dict:
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        if not payload.get("data"):
            raise RuntimeError(f"GraphQL request failed with {len(payload['errors'])} error(s)")
        # Error messages can contain private repository names, and Action logs are public.
        print(f"warning: ignored {len(payload['errors'])} partial GraphQL error(s)", file=sys.stderr)
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
            id
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
        "user_id": data["id"],
        "last_year": calendar["totalContributions"],
        "weeks": [week["contributionDays"] for week in calendar["weeks"]],
        "per_year": {y: data[f"y{y}"]["contributionCalendar"]["totalContributions"] for y in years},
        "repos_total": data["all"]["totalCount"],
        "repos_public": data["public"]["totalCount"],
        "languages": languages,
    }


def fetch_commit_times(token: str, user_id: str, since: datetime) -> list[datetime]:
    """Authored timestamps of the user's commits on default branches of all reachable repos."""
    variables = {"id": user_id, "since": since.isoformat()}
    repos = graphql(
        """query($id: ID!, $since: GitTimestamp!) {
          viewer { login }
          user(login: "%s") {
            repositories(first: 100, ownerAffiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER]) {
              nodes {
                owner { login }
                name
                defaultBranchRef { target { ... on Commit { history(since: $since, author: {id: $id}) { totalCount } } } }
              }
            }
          }
        }"""
        % USERNAME,
        token,
        variables,
    )["user"]["repositories"]["nodes"]

    times = []
    for repo in repos:
        target = ((repo or {}).get("defaultBranchRef") or {}).get("target") or {}
        if not target.get("history", {}).get("totalCount"):
            continue
        cursor = None
        while True:
            history = graphql(
                """query($owner: String!, $name: String!, $id: ID!, $since: GitTimestamp!, $cursor: String) {
                  repository(owner: $owner, name: $name) {
                    defaultBranchRef { target { ... on Commit {
                      history(first: 100, after: $cursor, since: $since, author: {id: $id}) {
                        pageInfo { hasNextPage endCursor }
                        nodes { authoredDate }
                      }
                    } } }
                  }
                }""",
                token,
                {**variables, "owner": repo["owner"]["login"], "name": repo["name"], "cursor": cursor},
            )["repository"]["defaultBranchRef"]["target"]["history"]
            times += [
                datetime.fromisoformat(node["authoredDate"].replace("Z", "+00:00")).astimezone(TIMEZONE)
                for node in history["nodes"]
            ]
            if not history["pageInfo"]["hasNextPage"]:
                break
            cursor = history["pageInfo"]["endCursor"]
    return times


def number(value: int, lang: dict) -> str:
    return f"{value:,}".replace(",", lang["thousands"])


def bar(share: float, width: int) -> str:
    filled = round(share * width)
    return "█" * filled + "░" * (width - filled)


def monthly_totals(days: list[dict]) -> list[tuple[date, int, int]]:
    """(first day of month, contributions, active days), oldest first."""
    totals: dict[date, list[int]] = {}
    for day in days:
        month = date.fromisoformat(day["date"]).replace(day=1)
        entry = totals.setdefault(month, [0, 0])
        entry[0] += day["contributionCount"]
        entry[1] += day["contributionCount"] > 0
    return [(month, total, active) for month, (total, active) in sorted(totals.items())]


def render_stats(metrics: dict, now: datetime, lang: dict) -> str:
    years = sorted(metrics["per_year"])
    trend = " → ".join(number(metrics["per_year"][y], lang) for y in years)

    total = sum(metrics["languages"].values()) or 1
    ranked = sorted(metrics["languages"].items(), key=lambda item: item[1], reverse=True)
    rows = ranked[:TOP_LANGUAGES]
    rest = sum(size for _, size in ranked[TOP_LANGUAGES:])
    if rest:
        rows.append((lang["others"], rest))
    chart = "\n".join(f"{name:<12} {bar(size / total, BAR_WIDTH)}  {size / total * 100:4.1f} %" for name, size in rows)

    header = lang["stats_header"].format(years=" → ".join(map(str, years)))
    public = f'{metrics["repos_public"]} {lang["public"]}'
    note = lang["stats_note"].format(year=years[-1], date=now.astimezone(TIMEZONE).strftime(lang["date"]))
    return f"""{header}
|:---:|:---:|:---:|
| **{number(metrics["last_year"], lang)}** | **{metrics["repos_total"]}** ({public}) | **{trend}** |

```text
{chart}
```

<sub>{note}</sub>"""


def activity_insights(days: list[dict], today: date, lang: dict) -> dict:
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
        # GitHub counts weekdays from Sunday = 0; LANGS lists them from Monday.
        per_weekday[(day["weekday"] - 1) % 7] += day["contributionCount"]

    best = max(days, key=lambda d: d["contributionCount"], default=None)
    last = date.fromisoformat(active[-1]["date"]) if active else None
    return {
        "status": "UP" if last and today - last <= IDLE_AFTER else "OUT_OF_SERVICE",
        "lastContribution": last.isoformat() if last else None,
        "currentStreakDays": current,
        "longestStreakDays": longest,
        "activeDays": f"{len(active)} / {len(days)}",
        "busiestWeekday": lang["weekdays"][per_weekday.index(max(per_weekday))],
        "bestDay": lang["best_day"].format(date=best["date"], n=best["contributionCount"]) if best else None,
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


def render_rhythm(times: list[datetime], lang: dict) -> str:
    request = f"""```http
GET /actuator/metrics/commits.hour HTTP/1.1
Host: github.com/{USERNAME}
```"""
    if not times:
        return f"{request}\n\n{lang['no_commits']}"

    total = len(times)
    slots = Counter(t.hour // 6 for t in times)
    weekend = sum(t.weekday() >= 5 for t in times)
    peak = Counter(t.hour for t in times).most_common(1)[0][0]

    lines = [lang["rhythm_title"].format(n=number(total, lang), tz=TIMEZONE.key), ""]
    for index, name in enumerate(lang["slots"]):
        share = slots[index] / total
        lines.append(
            f"{name:<11} {index * 6:02d}–{index * 6 + 6:02d}  {bar(share, RHYTHM_BAR_WIDTH)}  {share * 100:3.0f} %"
        )
    lines.append("")
    for name, count in ((lang["workdays"], total - weekend), (lang["weekend"], weekend)):
        share = count / total
        lines.append(f"{name:<11}        {bar(share, RHYTHM_BAR_WIDTH)}  {share * 100:3.0f} %")
    lines += ["", f"{lang['peak_hour']}: {peak:02d}:00–{peak + 1:02d}:00"]
    body = "\n".join(lines)
    return f"{request}\n\n```text\n{body}\n```"


def render_changelog(days: list[dict], today: date, lang: dict) -> str:
    months = monthly_totals(days)
    rows = []
    for index in range(len(months) - 1, max(len(months) - 1 - CHANGELOG_MONTHS, 0), -1):
        month, total, active = months[index]
        previous = months[index - 1][1]
        arrow = "▲" if total > previous else "▼" if total < previous else "="
        row = lang["changelog_row"].format(n=f"{number(total, lang):>5}", d=f"{active:>2}")
        ongoing = lang["ongoing"] if month == today.replace(day=1) else ""
        rows.append(f"[{month:%Y.%m}]  {arrow}  {row}{ongoing}")
    body = "\n".join(rows)
    return f"```text\n{body}\n```"


def render_heatmap(weeks: list[list[dict]], total: int, theme: dict, lang: dict) -> str:
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

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<g fill="{theme["text"]}" {FONT}>',
    ]

    last_label_week = -10
    for index, week in enumerate(weeks):
        month = date.fromisoformat(week[0]["date"]).month
        previous = date.fromisoformat(weeks[index - 1][0]["date"]).month if index else None
        if month != previous and index - last_label_week >= 3:
            parts.append(f'<text x="{left + index * step}" y="{top - 7}">{lang["months"][month - 1]}</text>')
            last_label_week = index
    for row, label in zip((1, 3, 5), lang["weekday_rows"]):
        parts.append(f'<text x="0" y="{top + row * step + 9}">{label}</text>')

    legend_y = top + 7 * step + 10
    parts.append(
        f'<text x="{left}" y="{legend_y + 9}">{lang["heatmap_total"].format(n=number(total, lang))}</text>'
    )
    legend_x = width - 10 - 5 * step - 66
    parts.append(f'<text x="{legend_x}" y="{legend_y + 9}">{lang["less"]}</text>')
    parts.append(f'<text x="{legend_x + 42 + 5 * step + 2}" y="{legend_y + 9}">{lang["more"]}</text>')
    parts.append("</g>")

    for index, week in enumerate(weeks):
        for day in week:
            x, y = left + index * step, top + day["weekday"] * step
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{color(day["contributionCount"])}"/>'
            )
    for i, fill in enumerate([theme["empty"], *theme["levels"]]):
        parts.append(
            f'<rect x="{legend_x + 42 + i * step}" y="{legend_y}" width="{cell}" height="{cell}" rx="2" fill="{fill}"/>'
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def render_trend(days: list[dict], theme: dict, lang: dict) -> str:
    months = monthly_totals(days)[-TREND_MONTHS:]
    width, height = 720, 170
    left, right, top, bottom = 24, 24, 40, 30
    base = height - bottom
    peak_value = max((total for _, total, _ in months), default=0) or 1
    step = (width - left - right) / max(len(months) - 1, 1)
    points = [
        (left + i * step, top + (1 - total / peak_value) * (base - top)) for i, (_, total, _) in enumerate(months)
    ]

    line = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(points))
    area = f"{line} L{points[-1][0]:.1f},{base} L{points[0][0]:.1f},{base} Z"
    peak_index = max(range(len(months)), key=lambda i: months[i][1])

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<text x="{left}" y="14" fill="{theme["text"]}" {FONT}>{lang["trend_title"]}</text>',
        f'<line x1="{left}" y1="{base}" x2="{width - right}" y2="{base}" stroke="{theme["text"]}" stroke-opacity="0.3"/>',
        f'<path d="{area}" fill="{theme["line"]}" fill-opacity="0.15"/>',
        f'<path d="{line}" fill="none" stroke="{theme["line"]}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>',
        f'<g fill="{theme["text"]}" {FONT} text-anchor="middle">',
    ]
    for i, ((x, y), (month, total, _)) in enumerate(zip(points, months)):
        parts.append(f'<text x="{x:.1f}" y="{height - 10}">{lang["months"][month.month - 1]}</text>')
        if i in (peak_index, len(months) - 1):
            parts.append(f'<text x="{x:.1f}" y="{y - 9:.1f}">{number(total, lang)}</text>')
    parts.append("</g>")
    for x, y in points:
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{theme["line"]}"/>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def replace_block(readme: str, name: str, content: str) -> str:
    start, end = f"<!-- {name}:START -->", f"<!-- {name}:END -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(readme):
        raise ValueError(f"Markers {start} / {end} not found")
    return pattern.sub(lambda _: f"{start}\n{content}\n{end}", readme)


def main() -> int:
    token = os.environ.get("GH_TOKEN")
    if not token:
        print("GH_TOKEN is not set", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    today = now.astimezone(TIMEZONE).date()
    metrics = fetch_metrics(token, now)
    days = [day for week in metrics["weeks"] for day in week]
    commit_times = fetch_commit_times(token, metrics["user_id"], now - timedelta(days=365))

    ASSETS.mkdir(exist_ok=True)
    for lang in LANGS.values():
        path = ROOT / lang["readme"]
        readme = path.read_text(encoding="utf-8")
        blocks = {
            "HEALTH": render_health(activity_insights(days, today, lang)),
            "STATS": render_stats(metrics, now, lang),
            "RHYTHM": render_rhythm(commit_times, lang),
            "CHANGELOG": render_changelog(days, today, lang),
        }
        try:
            for name, content in blocks.items():
                readme = replace_block(readme, name, content)
        except ValueError as error:
            print(f"{lang['readme']}: {error}", file=sys.stderr)
            return 1
        path.write_text(readme, encoding="utf-8")

        for theme_name, theme in THEMES.items():
            suffix = f"{theme_name}{lang['suffix']}.svg"
            heatmap = render_heatmap(metrics["weeks"], metrics["last_year"], theme, lang)
            (ASSETS / f"activity-{suffix}").write_text(heatmap, encoding="utf-8")
            (ASSETS / f"trend-{suffix}").write_text(render_trend(days, theme, lang), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
