"""PR file-overlap "style" feature: how often a merged PR touches files that other PRs
merged in the previous W days already touched (W = 14 and 28), for every repo of 2022-2026.

Files per PR come from git, not the API: the commit oids in data/github/<year>/<repo>/prs.json,
non-merge commits only, union of the files they changed (no rename detection). Lockfiles,
dependency/build directories, minified and generated files are dropped ("all"); "code" keeps
only the source extensions of 20_file_detect.py (the primary variant).

    scripts/23_pr_overlap.py                      # every repo -> results/pr_overlap/
    scripts/23_pr_overlap.py --only 2025/REPO     # one repo (year/repo or repo) -> logs/pr_overlap/test/
    scripts/23_pr_overlap.py --out DIR            # write somewhere else

Outputs hold no GitHub logins. Definitions: results/pr_overlap/DATA_DICTIONARY.md,
assumptions and open cases: results/pr_overlap/ASSUMPTIONS.md. No models, no API calls.
"""
import argparse
import importlib.util
import json
import re
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from common import LOGS, RESULTS, ROOT, read_selection, repo_dir

GITHUB = ROOT / "data" / "github"
OUT = RESULTS / "pr_overlap"
TEST_OUT = LOGS / "pr_overlap" / "test"
WINDOWS = (14, 28)
VARIANTS = ("code", "all")  # code is primary
DAY = 86400


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_scan = _load("sonar_scan", "03_sonar_scan.py")
_sonar_extra = _load("sonar_extra", "03b_sonar_extra.py")
_detect = _load("file_detect", "20_file_detect.py")
_process = _load("process_metrics", "08_process_metrics.py")
_extra_gh = _load("github_extra", "07b_github_extra.py")

# directories the SonarQube scans exclude (node_modules, dist, build, ...), as in 20_file_detect.py
SONAR_DIRS = set(re.findall(r"\*\*/([^/*]+)/\*\*", _scan.EXCLUSIONS))
KEEP_BUILD = _scan.KEEP_BUILD
VENDORED = _sonar_extra.VENDORED
VENDOR_DIRS = _detect.DETECTOR_ONLY_DIRS
GENERATED = _detect.DECLARATION_OR_GENERATED
CODE_EXT = set(_detect.EXT_LANG)
LOCKFILES = {"package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
             "poetry.lock", "pipfile.lock", "uv.lock", "composer.lock", "gemfile.lock", "cargo.lock",
             "go.sum", "pubspec.lock", "packages.lock.json", "gradle.lockfile", "podfile.lock",
             "mix.lock", "flake.lock"}
JUNK = re.compile(r"\.(map|pyc|pyo)$|(^|/)\.DS_Store$|\.min\.(js|css)$", re.I)


def ts(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


# ----------------------------------------------------------------------------- file hygiene

def excluded(repo, path):
    """True for lockfiles, dependency/build directories, minified and generated files."""
    parts = path.split("/")
    name = parts[-1]
    if name.lower() in LOCKFILES or name.endswith(".lock") or JUNK.search(path):
        return True
    dirs = SONAR_DIRS - ({"build"} if repo in KEEP_BUILD else set())
    if any(d in dirs for d in parts[:-1]):
        return True
    if repo in VENDORED and f"/{VENDORED[repo].strip('*').strip('/')}/" in f"/{path}":
        return True
    return bool(VENDOR_DIRS.search(path) or GENERATED.search(path))


def is_code(path):
    name = path.rsplit("/", 1)[-1]
    return "." in name and "." + name.rsplit(".", 1)[-1].lower() in CODE_EXT


def is_bot_login(login):
    """The 08 rule (GraphQL returns bot logins without the [bot] suffix, so [bot] alone misses
    github-classroom, github-actions, ...) is a superset of 'ends in [bot] or contains dependabot'."""
    return _process.is_bot("", "", login or "")


def is_bot_spec(login):
    low = (login or "").lower()
    return low.endswith("[bot]") or "dependabot" in low


# ----------------------------------------------------------------------------- files from git

def commit_files(path, oids):
    """({oid: set of files} for non-merge commits, set of oids missing locally, set of merge oids)."""
    oids = sorted(set(oids))
    if not oids:
        return {}, set(), set()
    chk = subprocess.run(["git", "-C", str(path), "cat-file", "--batch-check"], input="\n".join(oids) + "\n",
                         capture_output=True, text=True, check=True).stdout.splitlines()
    present, missing = [], set()
    for line in chk:
        parts = line.split()
        if len(parts) == 3 and parts[1] == "commit":
            present.append(parts[0])
        else:
            missing.add(parts[0])
    files = {}
    if present:
        out = subprocess.run(["git", "-C", str(path), "-c", "core.quotepath=false", "log", "--no-walk=unsorted",
                              "--no-merges", "--no-renames", "--name-only", "--format=%x1e%H", "--stdin"],
                             input=("\n".join(present) + "\n").encode(), capture_output=True, check=True).stdout
        for rec in out.decode("utf-8", errors="replace").split("\x1e")[1:]:
            lines = rec.split("\n")
            files[lines[0].strip()] = {l for l in lines[1:] if l}
    return files, missing, set(present) - set(files)


def pr_file_record(pr, files, missing):
    """Raw file set of one PR plus the commit bookkeeping."""
    listed = [n["commit"]["oid"] for n in pr["commits"]["nodes"]]
    raw = set()
    for oid in listed:
        raw |= files.get(oid, set())
    total = pr["commits"]["totalCount"]
    n_missing = sum(1 for o in listed if o in missing)
    return raw, {"commits_total": total, "commits_listed": len(listed),
                 "commits_nonmerge": sum(1 for o in listed if o in files),
                 "commits_missing_locally": n_missing,
                 "files_complete": total <= len(listed) and n_missing == 0}


# ----------------------------------------------------------------------------- overlap

def overlap(items, window_days):
    """items: [(merged_t, pr_number, set of files)] of the PRs of ONE repo and variant.
    Returns {pr_number: (share, any, n_ref_prs, n_ref_files)}. The reference set of a PR is the files
    of every other PR with merged_t in (t - W days, t); PRs with an identical merged_t are ordered
    by number, so the lower number counts as earlier. A PR with no PR in its window has no history to
    overlap with: share and any are None (undefined), not 0."""
    items = sorted(items, key=lambda x: (x[0], x[1]))
    out = {}
    for i, (t, num, files) in enumerate(items):
        ref, n_prs, j = set(), 0, i - 1
        while j >= 0 and items[j][0] > t - window_days * DAY:
            ref |= items[j][2]
            n_prs += 1
            j -= 1
        if not n_prs:
            out[num] = (None, None, 0, 0)
            continue
        hit = len(files & ref)
        out[num] = (hit / len(files), int(hit > 0), n_prs, len(ref))
    return out


def iso_week(t):
    y, w, _ = datetime.fromtimestamp(t, timezone.utc).isocalendar()
    return f"{y}-W{w:02d}"


def week_start(t):
    d = datetime.fromtimestamp(t, timezone.utc).date()
    return d - timedelta(days=d.weekday())


def default_branch(year, folder, prs):
    meta = GITHUB / str(year) / folder / "meta.json"
    if meta.exists():
        return json.loads(meta.read_text())["default_branch"], "github"
    p = subprocess.run(["git", "-C", str(repo_dir(year, folder)), "symbolic-ref", "-q", "refs/remotes/origin/HEAD"],
                       capture_output=True, text=True)
    if p.returncode == 0:
        return p.stdout.strip().removeprefix("refs/remotes/origin/"), "origin/HEAD"
    bases = pd.Series([p["baseRefName"] for p in prs if p["mergedAt"]]).mode()
    return (bases.iloc[0] if len(bases) else ""), "most_common_base"


# ----------------------------------------------------------------------------- one repo

def measure(year, folder):
    """(pr_level rows, validation rows, exclusion counts) for one repo."""
    path = repo_dir(year, folder)
    prs = json.loads((GITHUB / str(year) / folder / "prs.json").read_text())
    dbranch, _ = default_branch(year, folder, prs)
    bases = {p["baseRefName"] for p in prs}  # a PR whose head branch is another PR's base integrates (dev -> main)
    files, missing, _ = commit_files(path, [n["commit"]["oid"] for p in prs for n in p["commits"]["nodes"]])
    rows, val = [], []
    excl = {"bot": 0, "bot_beyond_spec": 0, "no_files": 0}
    for pr in prs:
        raw, info = pr_file_record(pr, files, missing)
        val.append({"year": year, "repo": folder, "pr_number": pr["number"], "merged": bool(pr["mergedAt"]),
                    "files_complete": info["files_complete"], "n_files_raw": len(raw),
                    "changed_files": pr["changedFiles"]})
        if not pr["mergedAt"]:
            continue
        login = (pr["author"] or {}).get("login", "")
        if is_bot_login(login):
            excl["bot"] += 1
            excl["bot_beyond_spec"] += not is_bot_spec(login)
            continue
        f_all = {f for f in raw if not excluded(folder, f)}
        if not f_all:
            excl["no_files"] += 1
            continue
        t = ts(pr["mergedAt"])
        base = pr["baseRefName"]
        flags = []
        if base != dbranch:
            flags.append("non_default_base")
        if not info["files_complete"]:
            flags.append("files_incomplete")
        if pr["headRefName"] in bases and pr["headRefName"] != base:
            flags.append("integration_pr")
        if _process.is_agent("", "", login):
            flags.append("ai_agent_author")
        rows.append({"year": year, "repo": folder, "pr_number": pr["number"], "_t": t,
                     "merged_at": datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "merged_week": iso_week(t), "n_files_raw": len(raw), "n_files_all": len(f_all),
                     "n_files_code": sum(is_code(f) for f in f_all), "base_branch": base,
                     "is_default_branch": base == dbranch, **info, "flags": ";".join(flags),
                     "_all": f_all, "_code": {f for f in f_all if is_code(f)}})
    if rows:
        t0 = min(r["_t"] for r in rows)
        for r in rows:
            r["days_since_first_merge"] = round((r["_t"] - t0) / DAY, 2)
        for v in VARIANTS:
            for w in WINDOWS:
                res = overlap([(r["_t"], r["pr_number"], r["_" + v]) for r in rows if r["_" + v]], w)
                # sensitivity: release PRs are neither measured nor part of any reference set (they re-date old work)
                res_ex = overlap([(r["_t"], r["pr_number"], r["_" + v]) for r in rows
                                  if r["_" + v] and "integration_pr" not in r["flags"]], w)
                for r in rows:
                    r[f"overlap_share_{v}_{w}_excl_integration"] = res_ex.get(r["pr_number"], (None,))[0]
                    share, any_, n_prs, n_files = res.get(r["pr_number"], (None,) * 4)
                    r[f"overlap_share_{v}_{w}"] = share
                    r[f"overlap_any_{v}_{w}"] = any_
                    r[f"ref_prs_{v}_{w}"] = n_prs
                    r[f"ref_files_{v}_{w}"] = n_files
    return rows, val, excl


# ----------------------------------------------------------------------------- aggregation

def weekly_table(year, folder, df):
    t = df._t
    first, last = week_start(t.min()), week_start(t.max())
    weeks = [first + timedelta(days=7 * i) for i in range((last - first).days // 7 + 1)]
    wk = df._t.map(week_start)
    out = []
    for i, w in enumerate(weeks):
        g = df[wk == w]
        row = {"year": year, "repo": folder, "week_index": i, "iso_week": f"{w.isocalendar()[0]}-W{w.isocalendar()[1]:02d}",
               "week_start": w.isoformat(), "n_prs": len(g)}
        for v in VARIANTS:
            for W in WINDOWS:
                s = g[f"overlap_share_{v}_{W}"].dropna()
                row[f"n_defined_{v}_{W}"] = len(s)
                row[f"mean_overlap_share_{v}_{W}"] = s.mean() if len(s) else None
                row[f"share_prs_overlap_ge_half_{v}_{W}"] = (s >= 0.5).mean() if len(s) else None
        out.append(row)
    return out


def ols_slope(y):
    return float(np.polyfit(np.arange(len(y)), y, 1)[0]) if len(y) >= 3 else None


def repo_table(year, folder, df, weekly, excl, val):
    t0, t1 = df._t.min(), df._t.max()
    row = {"year": year, "repo": folder, "n_merged_prs": len(df), "n_excluded_bot": excl["bot"],
           "n_excluded_bot_beyond_spec": excl["bot_beyond_spec"], "n_excluded_no_files": excl["no_files"],
           "first_merged": datetime.fromtimestamp(t0, timezone.utc).date().isoformat(),
           "last_merged": datetime.fromtimestamp(t1, timezone.utc).date().isoformat(),
           "span_days": round((t1 - t0) / DAY, 1), "n_weeks": len(weekly),
           "median_files_all": df.n_files_all.median(), "median_files_code": df.n_files_code.median(),
           "share_prs_no_code_files": (df.n_files_code == 0).mean(),
           "share_files_incomplete": (~df.files_complete).mean(),
           "share_non_default_base": (~df.is_default_branch).mean(),
           "share_ai_agent_author": df["flags"].str.contains("ai_agent_author").mean(),
           "n_integration_prs": int(df["flags"].str.contains("integration_pr").sum())}
    mid = t0 + (t1 - t0) / 2
    halves = {}
    if t1 > t0:
        halves = {"first": df[df._t < mid], "second": df[df._t >= mid]}
        row["prs_first_half"], row["prs_second_half"] = len(halves["first"]), len(halves["second"])
        row["half_ratio"] = row["prs_second_half"] / row["prs_first_half"] if row["prs_first_half"] else None
    row["weekly_pr_count_slope"] = ols_slope([w["n_prs"] for w in weekly])
    for v in VARIANTS:
        for W in WINDOWS:
            col, anycol = f"overlap_share_{v}_{W}", f"overlap_any_{v}_{W}"
            s = df[col].dropna()
            row[f"n_defined_{v}_{W}"] = len(s)
            row[f"mean_overlap_share_{v}_{W}"] = s.mean() if len(s) else None
            row[f"mean_overlap_any_{v}_{W}"] = df[anycol].dropna().mean() if len(s) else None
            row[f"share_prs_overlap_ge_half_{v}_{W}"] = (s >= 0.5).mean() if len(s) else None
            s2 = df[f"{col}_excl_integration"].dropna()
            row[f"mean_overlap_share_{v}_{W}_excl_integration"] = s2.mean() if len(s2) else None
            for name, g in halves.items():
                h = g[col].dropna()
                row[f"mean_overlap_share_{v}_{W}_{name}_half"] = h.mean() if len(h) else None
    return row


def validation_table(val):
    """Per year and per repo: PRs whose own commit list is complete, union of commit files
    (before any hygiene) vs GitHub's changedFiles."""
    df = pd.DataFrame(val)
    out = []

    def summarise(g, year, repo, scope):
        row = {"year": year, "repo": repo, "scope": scope, "n_prs_total": len(g),
               "n_prs_complete": int(g.files_complete.sum())}
        c = g[g.files_complete]
        row["share_incomplete"] = 1 - len(c) / len(g) if len(g) else None
        d = c[c.changed_files > 0]
        row["n_compared"] = len(d)
        if len(d):
            diff = d.n_files_raw - d.changed_files
            ratio = d.n_files_raw / d.changed_files
            row.update({"share_exact": (diff == 0).mean(), "share_within_1": (diff.abs() <= 1).mean(),
                        "share_union_larger": (diff > 0).mean(), "share_union_smaller": (diff < 0).mean(),
                        "median_ratio": ratio.median(), "ratio_p25": ratio.quantile(.25),
                        "ratio_p75": ratio.quantile(.75), "median_diff": diff.median()})
        return row

    for scope, g in (("all_prs", df), ("merged_prs", df[df.merged])):
        for year, gy in g.groupby("year"):
            out.append(summarise(gy, year, "ALL", scope))
        out.append(summarise(g, "ALL", "ALL", scope))
        for (year, repo), gr in g.groupby(["year", "repo"]):
            out.append(summarise(gr, year, repo, scope))
    return pd.DataFrame(out)


def year_summary(repo_df):
    num = [c for c in repo_df.columns if c not in ("year", "repo", "first_merged", "last_merged")
           and pd.api.types.is_numeric_dtype(repo_df[c])]
    notes = {2022: "n=4 repos; database has 1 PR and hot-desking-deploy 8, so most 2022 numbers rest on 2 repos. Descriptive only.",
             2026: "n=1 repo (the capstone). Descriptive only."}
    rows = []
    for year, g in repo_df.groupby("year"):
        for c in num:
            s = g[c].dropna()
            rows.append({"year": year, "metric": c, "n_repos_defined": len(s), "n_repos": len(g),
                         "median": s.median() if len(s) else None, "mean": s.mean() if len(s) else None,
                         "note": notes.get(year, "")})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- driver

def all_repos():
    items = [(year, repo) for _, repo, year in read_selection()]
    items += [(y, folder) for y, _, _, folder in _extra_gh.EXTRA]
    return sorted(items)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="one repo (year/repo or repo name); writes to logs/pr_overlap/test/")
    ap.add_argument("--out", help="output directory (default results/pr_overlap)")
    args = ap.parse_args()
    items = all_repos()
    if args.only:
        items = [i for i in items if args.only in (i[1], f"{i[0]}/{i[1]}")]
        if not items:
            raise SystemExit(f"{args.only} is not a known repo")
    out = TEST_OUT if args.only and not args.out else (Path(args.out) if args.out else OUT)
    out.mkdir(parents=True, exist_ok=True)

    pr_rows, weekly_rows, repo_rows, val_rows = [], [], [], []
    for year, folder in items:
        t = time.time()
        rows, val, excl = measure(year, folder)
        val_rows += val
        if rows:
            df = pd.DataFrame(rows)
            weekly = weekly_table(year, folder, df)
            weekly_rows += weekly
            repo_rows.append(repo_table(year, folder, df, weekly, excl, val))
            pr_rows += rows
        else:  # no analysable merged PR: keep the repo with its exclusion counts
            repo_rows.append({"year": year, "repo": folder, "n_merged_prs": 0, "n_excluded_bot": excl["bot"],
                              "n_excluded_bot_beyond_spec": excl["bot_beyond_spec"],
                              "n_excluded_no_files": excl["no_files"]})
        print(f"{year}/{folder}: {len(val)} PRs, {len(rows)} analysed, {time.time() - t:.1f}s", flush=True)

    keep = [c for c in pd.DataFrame(pr_rows).columns if not c.startswith("_")]
    pr_df = pd.DataFrame(pr_rows)[keep]
    ordered = ["year", "repo", "pr_number", "merged_at", "merged_week", "days_since_first_merge", "n_files_raw",
               "n_files_all", "n_files_code", "base_branch", "is_default_branch", "flags", "commits_total",
               "commits_listed", "commits_nonmerge", "commits_missing_locally", "files_complete"]
    pr_df = pr_df[ordered + [c for c in keep if c not in ordered]]
    repo_df = pd.DataFrame(repo_rows)
    pr_df.round(4).to_csv(out / "pr_level.csv", index=False)
    repo_df.round(4).to_csv(out / "repo_level.csv", index=False)
    pd.DataFrame(weekly_rows).round(4).to_csv(out / "weekly.csv", index=False)
    validation_table(val_rows).round(4).to_csv(out / "validation_changedfiles.csv", index=False)
    if not args.only:
        year_summary(repo_df).round(4).to_csv(out / "year_summary.csv", index=False)
    print(f"wrote {out}: {len(pr_df)} PR rows, {len(repo_df)} repos, {len(weekly_rows)} weeks")


if __name__ == "__main__":
    main()
