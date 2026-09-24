"""Merge inventory, SonarQube and Python metrics into results/results.csv.

One row per (repo, commit_sha) snapshot. Rows already in results.csv for other
commits (added later, e.g. for D3) are kept; rows for the same (repo, commit_sha)
are replaced.
"""
import subprocess

import pandas as pd

from common import RESULTS, repo_dir

KEY = ["cohort_year", "org", "repo", "commit_sha"]


def commit_date(year, repo, sha):
    return subprocess.run(["git", "-C", str(repo_dir(year, repo)), "show", "-s",
                           "--format=%cI", sha], check=True, capture_output=True,
                          text=True).stdout.strip()


def ratio(num, den, scale=100):
    num = pd.to_numeric(num, errors="coerce")
    den = pd.to_numeric(den, errors="coerce")
    return (scale * num / den.where(den > 0)).round(4)


def main():
    inv = pd.read_csv(RESULTS / "repo_inventory.csv", dtype={"section": str})
    sq = pd.read_csv(RESULTS / "sonarqube_metrics.csv")
    py = pd.read_csv(RESULTS / "custom_metrics.csv")
    status = pd.read_csv(RESULTS / "sonar_scan_status.csv", dtype=str)

    base = inv[["cohort_year", "org", "repo", "section", "team_key", "head_sha"]].rename(
        columns={"head_sha": "commit_sha"})
    base["snapshot_date"] = [commit_date(y, r, s) for y, r, s in
                             zip(base.cohort_year, base.repo, base.commit_sha)]

    # SonarQube and Python metrics must describe the same commit as the inventory
    sq = sq.merge(status[["project_key", "head_sha", "status", "notes"]], on="project_key", how="left")
    sq = sq.rename(columns={"head_sha": "commit_sha", "status": "sq_scan_status",
                            "notes": "sq_scan_notes"})
    sq = sq.drop(columns=["project_key"])
    sq["cohort_year"] = sq.cohort_year.astype(int)

    df = base.merge(sq, on=KEY, how="left").merge(py, on=KEY, how="left")

    # PDF comment % from SonarQube counts (comment_lines / ncloc, not comment_lines_density)
    df["sq_comment_pct_pdf"] = ratio(df.sq_comment_lines, df.sq_ncloc)
    df["sq_py_comment_pct_pdf"] = ratio(df.sq_py_comment_lines, df.sq_py_ncloc)
    df["sq_complexity_per_function"] = ratio(df.sq_complexity, df.sq_functions, scale=1)
    df["sq_issues_per_kloc"] = ratio(df.sq_violations, df.sq_ncloc, scale=1000)

    front = ["cohort_year", "org", "repo", "section", "team_key", "commit_sha", "snapshot_date"]
    sq_cols = sorted(c for c in df.columns if c.startswith("sq_"))
    py_cols = ["python_file_count"] + [c for c in py.columns if c.startswith("py_")]
    df = df[front + sq_cols + py_cols]

    out = RESULTS / "results.csv"
    if out.exists():
        old = pd.read_csv(out, dtype={"section": str})
        keep = old.merge(df[KEY], on=KEY, how="left", indicator=True)
        keep = keep[keep["_merge"] == "left_only"].drop(columns="_merge")
        df = pd.concat([keep, df], ignore_index=True)
    df = df.sort_values(["cohort_year", "repo", "snapshot_date"])
    df.to_csv(out, index=False)
    print(f"wrote results/results.csv ({len(df)} rows, {len(df.columns)} columns)")


if __name__ == "__main__":
    main()
