"""Refresh the metrics dashboard inside README.md.

Commits made to this profile repository itself are excluded from every metric:
the workflow pushes a README dashboard commit each day (authored as the profile
owner), which would otherwise keep the streak alive and pad the total forever.

Sources:
- Total commits: ``computed.commits`` field of ``metrics.json`` (produced by
  the ``lowlighter/metrics`` action) minus the commits authored in this
  repository. Falls back to the GraphQL yearly contribution count when
  ``metrics.json`` is missing or malformed.
- Current streak: computed from the GitHub GraphQL contribution calendar for
  the last 365 days, after subtracting this repository's own commits from each
  day. Today is treated as a soft gap if it has zero contributions so the
  streak doesn't reset just because the day isn't over.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
DEFAULT_USERNAME = "AgustinH09"
# Profile repository whose own commits must be ignored (the daily auto-commit
# would otherwise inflate the streak and total). Override with IGNORE_REPO.
DEFAULT_IGNORED_REPO = "AgustinH09/AgustinH09"


def generate_bar(percent: float, length: int = 10) -> str:
    percent = min(max(percent, 0), 100)
    filled = int(length * percent / 100)
    return "█" * filled + "░" * (length - filled)


def github_graphql(query: str, variables: dict, token: str) -> dict:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        GITHUB_GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "AgustinH09-readme-updater",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    if "errors" in body and body["errors"]:
        raise RuntimeError(f"GraphQL errors: {body['errors']}")
    return body["data"]


def fetch_contribution_calendar(username: str, token: str):
    today = date.today()
    one_year_ago = today - timedelta(days=365)
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        id
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    data = github_graphql(
        query,
        {
            "login": username,
            "from": f"{one_year_ago.isoformat()}T00:00:00Z",
            "to": f"{today.isoformat()}T23:59:59Z",
        },
        token,
    )
    user = data["user"]
    calendar = user["contributionsCollection"]["contributionCalendar"]
    days = []
    for week in calendar["weeks"]:
        for d in week["contributionDays"]:
            days.append((d["date"], d["contributionCount"]))
    days.sort()
    return calendar["totalContributions"], days, user["id"]


def fetch_repo_daily_commits(
    username: str, repo: str, token: str, days: int = 365, chunk: int = 90
) -> dict[str, int]:
    """Map of ISO date -> commits attributed to ``username`` in ``repo`` over the
    last ``days`` days.

    Queried in ``chunk``-day windows so the (un-paginated) per-repository
    contributions never exceed the 100-node page limit.
    """
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          commitContributionsByRepository(maxRepositories: 100) {
            repository { nameWithOwner }
            contributions(first: 100) {
              nodes { occurredAt commitCount }
            }
          }
        }
      }
    }
    """
    daily: dict[str, int] = {}
    today = date.today()
    target = repo.lower()
    window_start = today - timedelta(days=days)
    while window_start <= today:
        window_end = min(window_start + timedelta(days=chunk), today)
        data = github_graphql(
            query,
            {
                "login": username,
                "from": f"{window_start.isoformat()}T00:00:00Z",
                "to": f"{window_end.isoformat()}T23:59:59Z",
            },
            token,
        )
        by_repo = data["user"]["contributionsCollection"][
            "commitContributionsByRepository"
        ]
        for entry in by_repo:
            if entry["repository"]["nameWithOwner"].lower() != target:
                continue
            for node in entry["contributions"]["nodes"]:
                day = node["occurredAt"][:10]
                daily[day] = daily.get(day, 0) + (node["commitCount"] or 0)
        window_start = window_end + timedelta(days=1)
    return daily


def fetch_repo_authored_commits(repo: str, author_id: str, token: str) -> int:
    """Total commits authored by ``author_id`` on the default branch of ``repo``
    (given as ``owner/name``). Used to remove this repository's own commits from
    the grand total."""
    owner, _, name = repo.partition("/")
    if not owner or not name:
        return 0
    query = """
    query($owner: String!, $name: String!, $author: ID!) {
      repository(owner: $owner, name: $name) {
        defaultBranchRef {
          target {
            ... on Commit {
              history(author: {id: $author}) {
                totalCount
              }
            }
          }
        }
      }
    }
    """
    data = github_graphql(
        query, {"owner": owner, "name": name, "author": author_id}, token
    )
    repo_data = data.get("repository") or {}
    ref = repo_data.get("defaultBranchRef") or {}
    target = ref.get("target") or {}
    history = target.get("history") or {}
    return history.get("totalCount") or 0


def subtract_daily(
    days: list[tuple[str, int]], to_remove: dict[str, int]
) -> list[tuple[str, int]]:
    """Return ``days`` with ``to_remove`` counts subtracted per date (floored at 0)."""
    return [(day, max(0, count - to_remove.get(day, 0))) for day, count in days]


def compute_current_streak(days: list[tuple[str, int]]) -> int:
    """Walk the calendar from newest to oldest, counting consecutive
    non-zero days. The current day is allowed as a soft gap so the
    streak doesn't reset before the day is over."""
    if not days:
        return 0
    today_iso = date.today().isoformat()
    reversed_days = list(reversed(days))
    start = 0
    if reversed_days[0][0] == today_iso and reversed_days[0][1] == 0:
        start = 1
    streak = 0
    for _, count in reversed_days[start:]:
        if count > 0:
            streak += 1
        else:
            break
    return streak


def read_total_commits_from_metrics(metrics_path: str) -> int | None:
    if not os.path.exists(metrics_path):
        return None
    try:
        with open(metrics_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        print(f"Error reading {metrics_path}: {exc}", file=sys.stderr)
        return None
    value = data.get("computed", {}).get("commits")
    return value if isinstance(value, int) else None


def update_dashboard(readme_path: str, streak: int, total: int) -> bool:
    with open(readme_path, encoding="utf-8") as f:
        content = f.read()

    streak_pct = min(100, int(streak * 100 / 30))
    total_pct = 100 if total >= 1000 else max(0, int(total * 100 / 1000))

    dashboard_lines = [
        f"CONSISTENCY  [{generate_bar(streak_pct)}] {streak}d Streak",
        f"VOLUME       [{generate_bar(total_pct)}] {total}+ Total",
        "INTENSITY    [██████░░░░] TS/Rails",
    ]

    pattern = (
        r"(<!-- DASHBOARD_START -->\s*<pre>)(.*?)(</pre>\s*<!-- DASHBOARD_END -->)"
    )
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        print("Could not find DASHBOARD markers in README.md", file=sys.stderr)
        sys.exit(1)

    pre_open, inner, pre_close = match.group(1), match.group(2), match.group(3)
    lines = inner.splitlines()

    anchor = "CONSISTENCY"
    metrics_start = None
    metrics_col = 72
    for i, line in enumerate(lines):
        if anchor in line:
            metrics_start = i
            metrics_col = line.find(anchor)
            break
    if metrics_start is None:
        print(f"{anchor} marker not found inside <pre>", file=sys.stderr)
        sys.exit(1)

    new_lines = []
    for i, line in enumerate(lines):
        if metrics_start <= i < metrics_start + len(dashboard_lines):
            mountain = line[:metrics_col].ljust(metrics_col)
            new_lines.append(mountain + dashboard_lines[i - metrics_start])
        else:
            new_lines.append(line)

    new_inner = "\n".join(new_lines)
    if inner.endswith("\n") and not new_inner.endswith("\n"):
        new_inner += "\n"

    new_content = (
        content[: match.start()]
        + pre_open
        + new_inner
        + pre_close
        + content[match.end() :]
    )

    if new_content == content:
        return False

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    readme_path = os.path.join(root, "README.md")
    metrics_path = os.path.join(root, "metrics.json")

    if not os.path.exists(readme_path):
        print(f"README.md not found at {readme_path}", file=sys.stderr)
        return 1

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("METRICS_TOKEN")
    username = os.environ.get("GH_USERNAME", DEFAULT_USERNAME)
    ignored_repo = os.environ.get("IGNORE_REPO", DEFAULT_IGNORED_REPO)

    streak = 0
    yearly_total: int | None = None
    ignored_commits = 0
    ignored_daily: dict[str, int] = {}
    if token:
        try:
            yearly_total, days, user_id = fetch_contribution_calendar(username, token)
            try:
                ignored_daily = fetch_repo_daily_commits(username, ignored_repo, token)
                ignored_commits = fetch_repo_authored_commits(
                    ignored_repo, user_id, token
                )
            except (urllib.error.URLError, RuntimeError, KeyError) as exc:
                print(f"Self-repo exclusion fetch failed: {exc}", file=sys.stderr)
            streak = compute_current_streak(subtract_daily(days, ignored_daily))
        except (urllib.error.URLError, RuntimeError, KeyError) as exc:
            print(f"GraphQL fetch failed: {exc}", file=sys.stderr)
    else:
        print("No GITHUB_TOKEN/METRICS_TOKEN; skipping streak lookup.", file=sys.stderr)

    total = read_total_commits_from_metrics(metrics_path)
    if total is None:
        total = max(0, (yearly_total or 0) - sum(ignored_daily.values()))
    else:
        total = max(0, total - ignored_commits)

    changed = update_dashboard(readme_path, streak, total)
    if changed:
        print(f"README.md updated (streak={streak}d, total={total}).")
    else:
        print(f"README.md already up to date (streak={streak}d, total={total}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
