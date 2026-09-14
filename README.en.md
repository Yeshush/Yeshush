```text
__   __        _
\ \ / /__  ___| |__  _   _
 \ V / _ \/ __| '_ \| | | |
  | |  __/\__ \ | | | |_| |
  |_|\___||___/_| |_|\__,_|

 :: Solutions Engineer ::                             (Enterprise Edition)

INFO  --- [  main] profile.Yeshu  : Starting profile ...
INFO  --- [  main] profile.Yeshu  : Role         -> Solutions Engineer @ mesoneer
INFO  --- [  main] profile.Yeshu  : Backend      -> Java · Spring Boot
INFO  --- [  main] profile.Yeshu  : Frontend     -> Angular · TypeScript
INFO  --- [  main] profile.Yeshu  : Education    -> BSc Computer Science, ZHAW
INFO  --- [  main] profile.Yeshu  : Started profile, ready to connect.
```

[Deutsch](README.md) · **English**

## Profile

I build enterprise applications end to end: robust **Spring Boot** backends and
maintainable **Angular** frontends running in production at large organisations.
I care about clean interfaces, a clear layered architecture and code that stays
easy to understand years later.

## Status

<!-- HEALTH:START -->
```http
GET /actuator/health HTTP/1.1
Host: github.com/Yeshush
```

```json
{
  "status": "UP",
  "components": {
    "backend": {
      "status": "UP",
      "details": {
        "stack": "Java · Spring Boot"
      }
    },
    "frontend": {
      "status": "UP",
      "details": {
        "stack": "Angular · TypeScript"
      }
    },
    "activity": {
      "status": "UP",
      "details": {
        "lastContribution": "2026-09-15",
        "currentStreakDays": 2,
        "longestStreakDays": 6,
        "activeDays": "97 / 367",
        "busiestWeekday": "Monday",
        "bestDay": "2025-12-01 (115 contributions)"
      }
    }
  }
}
```
<!-- HEALTH:END -->

## Architecture I build

```mermaid
flowchart LR
    UI["Angular SPA<br/><sub>Components · Services · RxJS</sub>"]
    API["Spring Boot<br/><sub>REST Controller</sub>"]
    SVC["Business Logic<br/><sub>Services · Validation</sub>"]
    DATA["Persistence<br/><sub>Spring Data · JPA</sub>"]
    DB[("Database")]

    UI -- "REST / JSON" --> API --> SVC --> DATA --> DB
```

## Stack

| Area | Technologies |
|:--|:--|
| **Backend** | ![Java](https://img.shields.io/badge/Java-ED8B00?style=flat-square&logo=openjdk&logoColor=white) ![Spring Boot](https://img.shields.io/badge/Spring_Boot-6DB33F?style=flat-square&logo=springboot&logoColor=white) |
| **Frontend** | ![Angular](https://img.shields.io/badge/Angular-DD0031?style=flat-square&logo=angular&logoColor=white) ![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white) ![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=flat-square&logo=html5&logoColor=white) ![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=flat-square&logo=css3&logoColor=white) |
| **Data & Operations** | ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white) ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white) |
| **Also** | ![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) ![PHP](https://img.shields.io/badge/PHP-777BB4?style=flat-square&logo=php&logoColor=white) ![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat-square&logo=javascript&logoColor=black) ![C](https://img.shields.io/badge/C-00599C?style=flat-square&logo=c&logoColor=white) |

## Activity

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/activity-dark.en.svg"/>
  <img src="assets/activity-light.en.svg" alt="Contribution heatmap of the last 12 months"/>
</picture>

<!-- STATS:START -->
| Contributions (12 months) | Repositories | Contributions 2024 → 2025 → 2026* |
|:---:|:---:|:---:|
| **1,162** | **23** (5 public) | **289 → 643 → 704** |

```text
TypeScript   █████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░  43.1 %
PHP          ██████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  28.7 %
Python       ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   9.3 %
C            ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   5.9 %
JavaScript   ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   4.8 %
CSS          ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   4.4 %
Other        ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   3.8 %
```

<sub>Including private repositories · languages by code size · * 2026 to date · updated automatically on 2026-09-15</sub>
<!-- STATS:END -->

### Trend

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/trend-dark.en.svg"/>
  <img src="assets/trend-light.en.svg" alt="Contributions per month, last 12 months"/>
</picture>

### Work rhythm

<!-- RHYTHM:START -->
```http
GET /actuator/metrics/commits.hour HTTP/1.1
Host: github.com/Yeshush
```

```text
514 commits · last 12 months · time zone Europe/Zurich

Night       00–06  █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    4 %
Morning     06–12  █████░░░░░░░░░░░░░░░░░░░░░░░░░   15 %
Afternoon   12–18  ██████████░░░░░░░░░░░░░░░░░░░░   34 %
Evening     18–24  ██████████████░░░░░░░░░░░░░░░░   46 %

Weekdays           ████████████████████████████░░   92 %
Weekend            ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░    8 %

Peak hour: 20:00–21:00
```
<!-- RHYTHM:END -->

## Changelog

<!-- CHANGELOG:START -->
```text
[2026.09]  ▼  contributions    28 · active days  7  (in progress)
[2026.08]  ▲  contributions    55 · active days  5
[2026.07]  ▼  contributions     1 · active days  1
[2026.06]  ▼  contributions    36 · active days  6
[2026.05]  ▲  contributions   143 · active days 16
[2026.04]  ▼  contributions    86 · active days 11
```
<!-- CHANGELOG:END -->

## Contact

[![mesoneer](https://img.shields.io/badge/mesoneer-mesoneer.io-1F2937?style=flat-square)](https://mesoneer.io)
