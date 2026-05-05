"""Refresh the KAIZEN METRICS dashboard inside README.md.

Sources:
- Total commits: ``computed.commits`` field of ``metrics.json`` (produced by
  the ``lowlighter/metrics`` action). Falls back to the GraphQL yearly
  contribution count when ``metrics.json`` is missing or malformed.
- Current streak: computed from the GitHub GraphQL contribution calendar
  for the last 365 days. Today is treated as a soft gap if it has zero
  contributions so the streak doesn't reset just because the day isn't over.
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
    calendar = data["user"]["contributionsCollection"]["contributionCalendar"]
    days = []
    for week in calendar["weeks"]:
        for d in week["contributionDays"]:
            days.append((d["date"], d["contributionCount"]))
    days.sort()
    return calendar["totalContributions"], days


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
        "[ KAIZEN METRICS ]",
        "------------------",
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

    metrics_start = None
    metrics_col = 52
    for i, line in enumerate(lines):
        if "[ KAIZEN METRICS ]" in line:
            metrics_start = i
            metrics_col = line.find("[ KAIZEN METRICS ]")
            break
    if metrics_start is None:
        print("KAIZEN METRICS marker not found inside <pre>", file=sys.stderr)
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

    streak = 0
    yearly_total: int | None = None
    if token:
        try:
            yearly_total, days = fetch_contribution_calendar(username, token)
            streak = compute_current_streak(days)
        except (urllib.error.URLError, RuntimeError, KeyError) as exc:
            print(f"GraphQL fetch failed: {exc}", file=sys.stderr)
    else:
        print("No GITHUB_TOKEN/METRICS_TOKEN; skipping streak lookup.", file=sys.stderr)

    total = read_total_commits_from_metrics(metrics_path)
    if total is None:
        total = yearly_total or 0

    changed = update_dashboard(readme_path, streak, total)
    if changed:
        print(f"README.md updated (streak={streak}d, total={total}).")
    else:
        print(f"README.md already up to date (streak={streak}d, total={total}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
