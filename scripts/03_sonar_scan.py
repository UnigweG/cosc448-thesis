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

from common import (LOGS, RESULTS, load_env, project_key, read_selection, repo_dir,
                    sonar_get, sonar_session)

# site-packages catches virtualenvs committed under other names (e.g. myenv/Lib/site-packages)
EXCLUSIONS = ("**/node_modules/**,**/.venv/**,**/venv/**,**/dist/**,**/build/**,"
              "**/target/**,**/*.min.js,**/__pycache__/**,**/site-packages/**")

NEEDS_OTHER_SCANNER = {"C#": "C# needs SonarScanner for .NET (not analysed by the CLI scanner)",
                       "VB.NET": "VB.NET needs SonarScanner for .NET"}
NOT_IN_EDITION = {"C", "C++", "Objective-C", "Objective-C++", "Swift", "Dart", "PLpgSQL",
                  "TSQL", "ShaderLab", "HLSL", "Cython"}

LOG_DIR = LOGS / "sonar"

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
    return notes


def run_scanner(path, key, name, log_file, extra=(), exclusions=EXCLUSIONS):
    cmd = ["sonar-scanner",
           f"-Dsonar.host.url={os.environ['SONAR_HOST_URL']}",
           f"-Dsonar.projectKey={key}",
           f"-Dsonar.projectName={name}",
           "-Dsonar.sources=.",
           "-Dsonar.scm.disabled=true",
           f"-Dsonar.exclusions={exclusions}",
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
    items = read_selection()
    if args.only:
        items = [i for i in items if args.only in (i[1], f"{i[0]}/{i[1]}")]
        if not items:
            raise SystemExit(f"{args.only} is not in config/repo_selection.txt")

    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        results = list(pool.map(scan, items))

    print("waiting for SonarQube background tasks...")
    wait_for_queue(session)
    # the server can also fail a task after the scanner uploads successfully
    for r in results:
        if r["status"] != "ok":
            continue
        task = sonar_get(session, "/api/ce/activity", component=r["project_key"], ps=1)["tasks"]
        if task and task[0]["status"] != "SUCCESS":
            r["status"] = "failed"
            r["notes"] = "; ".join(filter(None, [r["notes"], "server task " + task[0]["status"]
                                               + ": " + task[0].get("errorMessage", "")[:200]]))
    missing = check_analyses(session, [r["project_key"] for r in results if r["status"] == "ok"])
    for r in results:
        if r["project_key"] in missing:
            r["status"] = "failed"
            r["notes"] = "; ".join(filter(None, [r["notes"], "no analysis on server"]))

    out = RESULTS / "sonar_scan_status.csv"
    old = {}
    if args.only and out.exists():
        with open(out) as f:
            old = {row["project_key"]: row for row in csv.DictReader(f)}
    for r in results:
        old[r["project_key"]] = r
    fields = ["cohort_year", "org", "repo", "project_key", "status", "notes", "head_sha"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(old.values(), key=lambda r: (str(r["cohort_year"]), r["repo"])))
    ok = sum(r["status"] == "ok" for r in results)
    print(f"{ok}/{len(results)} scanned ok; wrote results/sonar_scan_status.csv")


if __name__ == "__main__":
    main()
