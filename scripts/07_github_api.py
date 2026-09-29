"""Download pull requests (with commits and reviews) and issues for every selected repo
from the GitHub GraphQL API, through `gh api graphql`.

Raw JSON goes to data/github/<year>/<repo>/{prs,issues}.json (git-ignored, since it holds
GitHub logins). 08_process_metrics.py turns it into per-repo metrics.
Read only: the queries never write to GitHub.
"""
import argparse
import json
import subprocess
import time

from common import ROOT, read_selection, select

OUT = ROOT / "data" / "github"

PR_QUERY = """
query($owner: String!, $name: String!, $cursor: String, $n: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: $n, after: $cursor, orderBy: {field: CREATED_AT, direction: ASC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number createdAt mergedAt closedAt state isDraft
        author { login } mergedBy { login }
        baseRefName headRefName
        additions deletions changedFiles
        commits(first: 100) { totalCount
          nodes { commit { oid authoredDate author { name email user { login } } } } }
        comments { totalCount }
        reviews(first: 100) { totalCount
          nodes { author { login } state submittedAt comments { totalCount } } }
        reviewThreads { totalCount }
      }
    }
  }
}"""

ISSUE_QUERY = """
query($owner: String!, $name: String!, $cursor: String, $n: Int!) {
  repository(owner: $owner, name: $name) {
    issues(first: $n, after: $cursor, orderBy: {field: CREATED_AT, direction: ASC}) {
      pageInfo { hasNextPage endCursor }
      nodes { number createdAt closedAt state author { login } comments { totalCount } }
    }
  }
}"""


def fetch_page(query, owner, name, cursor, size):
    """One page; GitHub answers 502 when a page is too slow to build (large diffs), so
    retry with smaller pages."""
    while True:
        cmd = ["gh", "api", "graphql", "-F", f"owner={owner}", "-F", f"name={name}",
               "-F", f"n={size}", "-f", f"query={query}"]
        if cursor:
            cmd += ["-F", f"cursor={cursor}"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            return json.loads(proc.stdout)
        if size == 1:
            raise SystemExit(f"{owner}/{name}: {proc.stderr.strip()[:200]}")
        size = max(1, size // 3)
        time.sleep(2)


def fetch_all(query, owner, name, field, size):
    nodes, cursor = [], None
    while True:
        conn = fetch_page(query, owner, name, cursor, size)["data"]["repository"][field]
        nodes += conn["nodes"]
        if not conn["pageInfo"]["hasNextPage"]:
            return nodes
        cursor = conn["pageInfo"]["endCursor"]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="one repo (name or org/repo)")
    ap.add_argument("--refresh", action="store_true", help="re-download repos already saved")
    args = ap.parse_args()
    items = read_selection()
    if args.only:
        items = select(items, args.only)
    for org, repo, year in items:
        d = OUT / str(year) / repo
        if (d / "issues.json").exists() and not args.refresh:
            continue
        d.mkdir(parents=True, exist_ok=True)
        prs = fetch_all(PR_QUERY, org, repo, "pullRequests", 50)
        (d / "prs.json").write_text(json.dumps(prs))
        issues = fetch_all(ISSUE_QUERY, org, repo, "issues", 100)
        (d / "issues.json").write_text(json.dumps(issues))
        print(f"{org}/{repo}: {len(prs)} PRs, {len(issues)} issues")


if __name__ == "__main__":
    main()
