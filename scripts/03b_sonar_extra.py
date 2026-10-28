"""SonarQube for the two extra groups: 2022 (pre-AI baseline) and 2026 (the capstone).

These repos are not in config/repo_selection.txt (they are not on GitHub classroom orgs),
so they are listed here. Local clones live in data/repos/<year>/ (git clone --local from the
read-only originals, push URL disabled). Scanning, project keys and the exported columns are
the same as for 2023-25, so the years stack.

    scripts/03b_sonar_extra.py            # scan + export 2022 and 2026
    scripts/03b_sonar_extra.py --no-scan  # export only (projects already on the server)

Writes results/sonar_scan_status_2022_2026.csv, results/sonar_2022.csv, results/sonar_2026.csv.
"""
import argparse
import csv
import importlib.util
from collections import Counter

import pandas as pd

from common import (DATA, RESULTS, ROOT, counts_as_int, git, project_key, repo_dir,
                    sonar_get, sonar_session)


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


scan_mod = _load("sonar_scan", "03_sonar_scan.py")
export_mod = _load("sonar_export", "04_sonar_export.py")

# (year, org label, repo directory name under data/repos/<year>/)
EXTRA = [
    (2022, "UBCO-COSC-499-Summer-2022", "api-development-and-testing-project1-helpya-services-inc"),
    (2022, "UBCO-COSC-499-Summer-2022", "database"),
    (2022, "UBCO-COSC-499-Summer-2022", "hot-desking-deploy"),
    (2022, "UBCO-COSC-499-Summer-2022", "matlab-to-python-application-translation-project2-nrc"),
    (2026, "UBCOCOSC499-S2026", "capstone-project-team-11"),
]
# vendored third-party code committed into the repo (ckeditor, tinymce, ... under src/public/packages)
VENDORED = {"hot-desking-deploy": "**/public/packages/**"}
# source languages SonarQube Community Edition cannot analyse, by extension
UNANALYSED_EXT = {".m": "MATLAB", ".c": "C", ".h": "C/C++ header", ".cc": "C++", ".cpp": "C++",
                  ".hpp": "C++", ".cs": "C#", ".swift": "Swift", ".sql": "SQL (not analysed by CLI scanner)"}


def unanalysed_languages(path):
    files = git(path, "ls-files").splitlines()
    c = Counter(UNANALYSED_EXT[f[f.rfind("."):].lower()] for f in files
                if "." in f.rsplit("/", 1)[-1] and f[f.rfind("."):].lower() in UNANALYSED_EXT)
    return [f"{n} {lang} file(s) not analysed by SonarQube" for lang, n in c.items()]


def scan_one(item):
    year, org, repo = item
    path = repo_dir(year, repo)
    key = project_key(year, repo)
    log_file = scan_mod.LOG_DIR / f"{key}.log"
    notes = unanalysed_languages(path)
    exclusions = scan_mod.EXCLUSIONS
    if repo in VENDORED:
        exclusions += "," + VENDORED[repo]
        notes.append(f"vendored packages excluded ({VENDORED[repo]})")
    sha = git(path, "rev-parse", "HEAD")
    rc = scan_mod.run_scanner(path, key, f"{year}/{repo}", log_file, exclusions=exclusions)
    text = log_file.read_text(errors="replace")
    if rc != 0 and "sonar.java.binaries" in text:
        rc = scan_mod.run_scanner(path, key, f"{year}/{repo}", log_file,
                                  ["-Dsonar.java.binaries=."], exclusions)
        notes.append("retried with sonar.java.binaries=.")
        text = log_file.read_text(errors="replace")
    failed_files = text.count("Failed to analyze file")
    if failed_files:
        notes.append(f"{failed_files} file(s) failed analysis (see log)")
    if rc != 0:
        err = [l for l in text.splitlines() if "ERROR" in l]
        notes.append("error: " + (err[0][:200] if err else f"exit {rc}"))
    print(("ok" if rc == 0 else "failed"), key, flush=True)
    return {"cohort_year": year, "org": org, "repo": repo, "project_key": key,
            "status": "ok" if rc == 0 else "failed", "notes": "; ".join(notes), "head_sha": sha}


def export(session, rows_status):
    avail = export_mod.available_keys()
    keys = [k for k in export_mod.KEYS if k in avail]
    ok = {r["project_key"] for r in rows_status if r["status"] == "ok"}
    out = []
    for r in rows_status:
        key = r["project_key"]
        row = {"cohort_year": r["cohort_year"], "org": r["org"], "repo": r["repo"], "project_key": key}
        if key in ok:
            comp = sonar_get(session, "/api/measures/component", component=key,
                             metricKeys=",".join(keys))["component"]
            got = {m["metric"]: m.get("value") for m in comp["measures"]}
            for k in keys:
                row[f"sq_{k}"] = got.get(k)
            analyses = sonar_get(session, "/api/project_analyses/search", project=key, ps=1)["analyses"]
            row["sq_analysis_date"] = analyses[0]["date"] if analyses else None
            row.update(export_mod.python_totals(export_mod.file_measures(session, key)))
            row.update(export_mod.issue_facets(session, key))
        out.append(row)
    df = pd.DataFrame(out)
    # same column order as results/sonarqube_metrics.csv
    cols = list(pd.read_csv(RESULTS / "sonarqube_metrics.csv", nrows=0).columns)
    df = df.reindex(columns=cols)
    exported = df.project_key.isin(ok)
    for c in [c for c in df.columns if c.startswith("sq_issues_")]:
        df.loc[exported, c] = df.loc[exported, c].fillna(0)
    df = counts_as_int(df)
    for year in sorted(df.cohort_year.unique()):
        df[df.cohort_year == year].to_csv(RESULTS / f"sonar_{year}.csv", index=False)
        print(f"wrote results/sonar_{year}.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-scan", action="store_true")
    args = ap.parse_args()
    session = sonar_session()
    scan_mod.LOG_DIR.mkdir(parents=True, exist_ok=True)
    scan_mod.EMPTY_SETTINGS.write_text("")
    status_file = RESULTS / "sonar_scan_status_2022_2026.csv"
    if args.no_scan:
        with open(status_file) as f:
            status = list(csv.DictReader(f))
    else:
        status = [scan_one(i) for i in EXTRA]
        scan_mod.check_server(session, status)
        with open(status_file, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=scan_mod.STATUS_FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(status)
    export(session, status)


if __name__ == "__main__":
    main()
