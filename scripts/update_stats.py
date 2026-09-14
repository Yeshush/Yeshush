"""Fetch GitHub account metrics and rewrite the stats block in README.md.

Replaces everything between the STATS:START and STATS:END markers.
Needs a token in GH_TOKEN that can read the user's private repositories.
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USERNAME = os.environ.get("GH_USER", "Yeshush")
README = Path(__file__).resolve().parent.parent / "README.md"
START, END = "<!-- STATS:START -->", "<!-- STATS:END -->"
BAR_WIDTH = 48
TOP_LANGUAGES = 6
# Build/config languages that would distort the "what do I code in" picture.
IGNORED_LANGUAGES = {"Makefile", "Dockerfile", "Batchfile", "Shell"}


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
            lastYear: contributionsCollection {{ contributionCalendar {{ totalContributions }} }}
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

    return {
        "last_year": data["lastYear"]["contributionCalendar"]["totalContributions"],
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


def render(metrics: dict, now: datetime) -> str:
    years = sorted(metrics["per_year"])
    trend = " → ".join(swiss(metrics["per_year"][y]) for y in years)
    return f"""{START}
> Automatisch aktualisiert am {now:%d.%m.%Y} · inkl. privater Repositories

| 🔥 Contributions (letzte 12 Monate) | 📦 Eigene Repositories | 📈 {" → ".join(map(str, years))}* |
|:---:|:---:|:---:|
| **{swiss(metrics["last_year"])}** | **{metrics["repos_total"]}** ({metrics["repos_public"]} öffentlich) | **{trend}** |

<sub>* {years[-1]} bis heute.</sub>

**Meistgenutzte Sprachen** (nach Codemenge über alle eigenen Repos)

```text
{language_chart(metrics["languages"])}
```
{END}"""


def main() -> int:
    token = os.environ.get("GH_TOKEN")
    if not token:
        print("GH_TOKEN is not set", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    readme = README.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(readme):
        print(f"Markers {START} / {END} not found in README.md", file=sys.stderr)
        return 1

    block = render(fetch_metrics(token, now), now)
    README.write_text(pattern.sub(lambda _: block, readme), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
