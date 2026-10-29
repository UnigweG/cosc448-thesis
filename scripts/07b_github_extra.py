"""GitHub data for the two extra groups: 2022 (pre-AI baseline) and 2026 (the capstone).

Like 03b_sonar_extra.py, these five repos are not in config/repo_selection.txt, so they are
listed here. For each one this
  (a) downloads PRs and issues with the query and helpers of 07_github_api.py into
      data/github/<year>/<clone folder>/{prs,issues}.json, plus meta.json (default branch), and
  (b) fetches every PR head into the local clone under refs/pull/ (what 02_clone.sh does for 2023-25).
Read only: GraphQL queries and `git fetch`; nothing is written to GitHub.

    scripts/07b_github_extra.py            # skips repos already saved
    scripts/07b_github_extra.py --refresh  # download again
"""
import argparse
import importlib.util
import json
import subprocess

from common import ROOT, git, repo_dir


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


api = _load("github_api", "07_github_api.py")

# (year, GitHub org, GitHub repo, clone folder under data/repos/<year>/)
EXTRA = [
    (2022, "UBCO-COSC-499-Summer-2022", "api-development-and-testing-project1-helpya-services-inc",
     "api-development-and-testing-project1-helpya-services-inc"),
    (2022, "UBCO-COSC-499-Summer-2022", "database", "database"),
    (2022, "UBCO-COSC-499-Summer-2022", "hot-desking-deploy", "hot-desking-deploy"),
    (2022, "UBCO-COSC-499-Summer-2022", "matlab-to-python-application-translation-project2-nrc",
     "matlab-to-python-application-translation-project2-nrc"),
    # the GitHub repo is capstone-capstone-project-team-11, the clone folder capstone-project-team-11
    (2026, "UBCO-COSC499-S2026", "capstone-capstone-project-team-11", "capstone-project-team-11"),
]


def default_branch(org, repo):
    out = subprocess.run(["gh", "api", f"repos/{org}/{repo}", "--jq", ".default_branch"],
                         capture_output=True, text=True, check=True).stdout.strip()
    return out


def fetch_heads(year, org, repo, folder):
    path = repo_dir(year, folder)
    url = f"https://github.com/{org}/{repo}.git"
    subprocess.run(["git", "-C", str(path), "fetch", "--quiet", url,
                    "+refs/pull/*/head:refs/pull/*/head"], check=True)
    return len(git(path, "for-each-ref", "refs/pull").splitlines())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refresh", action="store_true", help="download repos already saved again")
    args = ap.parse_args()
    for year, org, repo, folder in EXTRA:
        d = api.OUT / str(year) / folder
        if not (d / "issues.json").exists() or args.refresh:
            d.mkdir(parents=True, exist_ok=True)
            prs = api.fetch_all(api.PR_QUERY, org, repo, "pullRequests", 50)
            (d / "prs.json").write_text(json.dumps(prs))
            issues = api.fetch_all(api.ISSUE_QUERY, org, repo, "issues", 100)
            (d / "issues.json").write_text(json.dumps(issues))
            (d / "meta.json").write_text(json.dumps({"org": org, "repo": repo,
                                                     "default_branch": default_branch(org, repo)}))
            print(f"{org}/{repo}: {len(prs)} PRs, {len(issues)} issues")
        refs = fetch_heads(year, org, repo, folder)
        print(f"{year}/{folder}: {refs} PR heads under refs/pull/")


if __name__ == "__main__":
    main()
