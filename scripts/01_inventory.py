"""List every repo in the three COSC 499 orgs (read only, no cloning).

Writes results/repo_inventory_all.csv. With --groups, prints the repos grouped by
name pattern so the capstone projects can be picked out.
"""
import argparse
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from common import ORGS, RESULTS

FIELDS = ("name,description,defaultBranchRef,primaryLanguage,diskUsage,createdAt,"
          "pushedAt,isArchived,url,visibility")
OUT = RESULTS / "repo_inventory_all.csv"


def gh_json(args):
    out = subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def list_org(org):
    repos = gh_json(["repo", "list", org, "--limit", "2000", "--json", FIELDS])
    rows = []
    for r in repos:
        rows.append({
            "cohort_year": ORGS[org],
            "org": org,
            "repo": r["name"],
            "description": (r.get("description") or "").replace("\n", " "),
            "default_branch": (r.get("defaultBranchRef") or {}).get("name", ""),
            "primary_language": (r.get("primaryLanguage") or {}).get("name", ""),
            "size_kb": r.get("diskUsage"),
            "created_at": r.get("createdAt"),
            "pushed_at": r.get("pushedAt"),
            "is_archived": r.get("isArchived"),
            "visibility": r.get("visibility"),
            "clone_url": r["url"] + ".git",
        })
    return rows


def languages(org, repo):
    try:
        return gh_json(["api", f"repos/{org}/{repo}/languages"])
    except subprocess.CalledProcessError:
        return None


def build_inventory():
    rows = []
    for org in ORGS:
        org_rows = list_org(org)
        print(f"{org}: {len(org_rows)} repos")
        rows += org_rows
    with ThreadPoolExecutor(max_workers=8) as pool:
        langs = list(pool.map(lambda r: languages(r["org"], r["repo"]), rows))
    for r, lang in zip(rows, langs):
        r["language_bytes"] = json.dumps(lang, sort_keys=True) if lang is not None else ""
    df = pd.DataFrame(rows).sort_values(["cohort_year", "repo"])
    df.to_csv(OUT, index=False)
    print(f"wrote {OUT.relative_to(RESULTS.parent)} ({len(df)} rows)")


def group_name(repo):
    """Strip team numbers, usernames and similar suffixes to get a name pattern."""
    name = repo.lower()
    name = re.sub(r"[-_ ]?(team|group|grp|t)[-_ ]?\d+.*$", "", name)
    name = re.sub(r"[-_]\d+$", "", name)
    return name


def show_groups(examples=False):
    df = pd.read_csv(OUT)
    # GitHub Classroom repos are named <assignment>-<username>, so group by the
    # longest assignment prefix shared by several repos in the same org.
    for org, sub in df.groupby("org", sort=True):
        names = sub["repo"].tolist()
        prefixes = {}
        for n in names:
            parts = re.split(r"(?<=[a-z0-9])-", n.lower())
            for i in range(1, len(parts)):
                p = "-".join(parts[:i])
                prefixes[p] = prefixes.get(p, 0) + 1
        def pattern(n):
            parts = re.split(r"(?<=[a-z0-9])-", n.lower())
            best = group_name(n)
            for i in range(len(parts) - 1, 0, -1):
                p = "-".join(parts[:i])
                if prefixes.get(p, 0) >= 3:
                    return p
            return best
        sub = sub.assign(group=sub["repo"].map(pattern))
        g = (sub.groupby("group")
                .agg(count=("repo", "size"),
                     examples=("repo", lambda s: ", ".join(list(s)[:3])),
                     median_size_kb=("size_kb", "median"),
                     langs=("primary_language", lambda s: ",".join(sorted(set(s.dropna().astype(str)))[:4])))
                .sort_values("count", ascending=False))
        # individual assignment repo names contain usernames, so only show them on request
        if not examples:
            g = g.drop(columns="examples")
        print(f"\n== {org} ({len(sub)} repos, {len(g)} groups)")
        with pd.option_context("display.width", 250, "display.max_colwidth", 80, "display.max_rows", 500):
            print(g.to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", action="store_true", help="only print groups from the saved CSV")
    ap.add_argument("--examples", action="store_true", help="also print 3 example repo names per group")
    args = ap.parse_args()
    if not args.groups:
        build_inventory()
    show_groups(args.examples)
