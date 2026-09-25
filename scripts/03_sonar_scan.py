"""Run sonar-scanner on every selected repo and wait for the server to process them.

Project key cosc448_<year>_<repo>, project name <year>/<repo>. The token is passed
to the scanner through the SONAR_TOKEN environment variable, never on the command line.

    scripts/03_sonar_scan.py                 # all repos, 3 at a time
    scripts/03_sonar_scan.py --only REPO     # one repo (repo name or org/repo)
"""
import argparse
import csv
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from common import (LOGS, RESULTS, load_env, project_key, read_selection, repo_dir,
                    sonar_get, sonar_session)

# site-packages catches virtualenvs committed under other names (e.g. myenv/Lib/site-packages)
EXCLUSIONS = ("**/node_modules/**,**/.venv/**,**/venv/**,**/dist/**,**/build/**,"
              "**/target/**,**/*.min.js,**/__pycache__/**,**/site-packages/**")

NEEDS_OTHER_SCANNER = {"C#": "C# needs SonarScanner for .NET (not analysed by the CLI scanner)",
                       "VB.NET": "VB.NET needs SonarScanner for .NET"}
NOT_IN_EDITION = {"C", "C++", "Objective-C", "Objective-C++", "Swift", "Dart", "PLpgSQL",
                  "TSQL", "ShaderLab", "HLSL", "Cython"}
# GitHub languages with no SonarQube analyser (SCSS and Vue are covered by the CSS and JS ones)
NO_ANALYSER = {"EJS"}

LOG_DIR = LOGS / "sonar"
# passed as project.settings so a team's own sonar-project.properties is never read
EMPTY_SETTINGS = LOG_DIR / "empty-sonar-project.properties"
STATUS_FIELDS = ["cohort_year", "org", "repo", "project_key", "status", "notes", "head_sha"]

# The starter template's build/ folder is meant for compiled output, but this team kept
# all of its source code there, so build/ is not excluded for this repo.
KEEP_BUILD = {"capstone-project-team-2-003-1"}


def head_sha(path):
    return subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()


def language_flags(org, repo):
    """Note languages (>= 5% of the repo's bytes) this setup cannot analyse."""
    import pandas as pd
    inv = pd.read_csv(RESULTS / "repo_inventory.csv")
    row = inv[(inv.org == org) & (inv.repo == repo)]
    if row.empty or pd.isna(row.iloc[0].language_bytes):
        return []
    langs = json.loads(row.iloc[0].language_bytes)
    total = sum(langs.values()) or 1
    notes = []
    for lang, b in sorted(langs.items(), key=lambda x: -x[1]):
        share = 100 * b / total
        if share < 5:
            continue
        if lang in NEEDS_OTHER_SCANNER:
            notes.append(f"{lang} {share:.0f}% not analysed ({NEEDS_OTHER_SCANNER[lang]})")
        elif lang in NOT_IN_EDITION:
            notes.append(f"{lang} {share:.0f}% not supported by Community Edition")
        elif lang in NO_ANALYSER:
            notes.append(f"{lang} {share:.0f}% not analysed (no SonarQube analyser)")
    return notes


def run_scanner(path, key, name, log_file, extra=(), exclusions=EXCLUSIONS):
    cmd = ["sonar-scanner",
           f"-Dsonar.host.url={os.environ['SONAR_HOST_URL']}",
           f"-Dsonar.projectKey={key}",
           f"-Dsonar.projectName={name}",
           "-Dsonar.sources=.",
           "-Dsonar.scm.disabled=true",
           f"-Dsonar.exclusions={exclusions}",
           f"-Dproject.settings={EMPTY_SETTINGS}",
           *extra]
    with open(log_file, "w") as log:
        proc = subprocess.run(cmd, cwd=path, stdout=log, stderr=subprocess.STDOUT,
                              env=os.environ.copy())
    return proc.returncode


def scan(item):
    org, repo, year = item
    path = repo_dir(year, repo)
    key = project_key(year, repo)
    log_file = LOG_DIR / f"{key}.log"
    notes = language_flags(org, repo)
    sha = head_sha(path)
    exclusions = EXCLUSIONS
    if repo in KEEP_BUILD:
        exclusions = ",".join(p for p in EXCLUSIONS.split(",") if p != "**/build/**")
        notes.append("build/ not excluded (source code lives there)")
    started = time.time()
    rc = run_scanner(path, key, f"{year}/{repo}", log_file, exclusions=exclusions)
    if rc != 0:
        text = log_file.read_text(errors="replace")
        if "sonar.java.binaries" in text:
            rc = run_scanner(path, key, f"{year}/{repo}", log_file, ["-Dsonar.java.binaries=."],
                             exclusions)
            notes.append("retried with sonar.java.binaries=.")
    status = "ok" if rc == 0 else "failed"
    failed_files = log_file.read_text(errors="replace").count("Failed to analyze file")
    if failed_files:
        notes.append(f"{failed_files} file(s) failed analysis (see log)")
    if rc != 0:
        err = [l for l in log_file.read_text(errors="replace").splitlines() if "ERROR" in l]
        notes.append("error: " + (err[0][:200] if err else f"exit {rc}"))
    print(f"{status:6} {key} ({time.time() - started:.0f}s)", flush=True)
    return {"cohort_year": year, "org": org, "repo": repo, "project_key": key,
            "status": status, "notes": "; ".join(notes), "head_sha": sha}


def wait_for_queue(session, timeout=3600):
    start = time.time()
    while time.time() - start < timeout:
        data = sonar_get(session, "/api/ce/activity", status="PENDING,IN_PROGRESS", ps=100)
        n = len(data["tasks"])
        if n == 0:
            return True
        print(f"  {n} background task(s) still queued/running", flush=True)
        time.sleep(15)
    return False


def add_note(r, note):
    r["notes"] = "; ".join(filter(None, [r["notes"], note]))


def check_server(session, results):
    """Update scan results with what the server did after the upload."""
    print("waiting for SonarQube background tasks...")
    if not wait_for_queue(session):
        # the latest task per project may still be an older analysis, so don't read it
        for r in results:
            if r["status"] == "ok":
                r["status"] = "pending"
                add_note(r, "queue timeout, task status not checked")
        return
    # the server can also fail a task after the scanner uploads successfully
    for r in results:
        if r["status"] != "ok":
            continue
        task = sonar_get(session, "/api/ce/activity", component=r["project_key"], ps=1)["tasks"]
        if task and task[0]["status"] != "SUCCESS":
            r["status"] = "failed"
            add_note(r, "server task " + task[0]["status"] + ": "
                     + task[0].get("errorMessage", "")[:200])
    missing = check_analyses(session, [r["project_key"] for r in results if r["status"] == "ok"])
    for r in results:
        if r["project_key"] in missing:
            r["status"] = "failed"
            add_note(r, "no analysis on server")


def write_status(results, only):
    out = RESULTS / "sonar_scan_status.csv"
    old = {}
    if only and out.exists():
        with open(out) as f:
            old = {row["project_key"]: row for row in csv.DictReader(f)}
    for r in results:
        old[r["project_key"]] = r
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=STATUS_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(old.values(), key=lambda r: (str(r["cohort_year"]), r["repo"])))


def check_analyses(session, keys):
    missing = []
    for key in keys:
        data = sonar_get(session, "/api/project_analyses/search", project=key, ps=1)
        if not data["analyses"]:
            missing.append(key)
    return missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="scan a single repo")
    ap.add_argument("--parallel", type=int, default=3)
    args = ap.parse_args()

    load_env()
    session = sonar_session()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    EMPTY_SETTINGS.write_text("")
    items = read_selection()
    if args.only:
        items = [i for i in items if args.only in (i[1], f"{i[0]}/{i[1]}")]
        if not items:
            raise SystemExit(f"{args.only} is not in config/repo_selection.txt")

    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        results = list(pool.map(scan, items))

    # written before the server checks, so a failing check still leaves the scan results
    write_status(results, args.only)
    try:
        check_server(session, results)
    except requests.HTTPError as e:
        if e.response is None or e.response.status_code != 403:
            raise
        raise SystemExit("SonarQube returned 403 on " + e.response.url.split("?")[0] + ". "
                         "SONAR_TOKEN must be a user token; a global analysis token (sqa_...) "
                         "can scan but not read /api/ce/activity. Scanner results are in "
                         "results/sonar_scan_status.csv without the server checks.")
    write_status(results, args.only)
    ok = sum(r["status"] == "ok" for r in results)
    print(f"{ok}/{len(results)} scanned ok; wrote results/sonar_scan_status.csv")


if __name__ == "__main__":
    main()
