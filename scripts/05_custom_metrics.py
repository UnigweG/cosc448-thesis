"""Supervisor's metrics (Radon, Pylint, Bandit) on each repo's tracked Python files.

Aggregation follows docs/metrics_definitions.md:
  CC      per-block values pooled across files -> mean (CCavg) and max (CCmax)
  MI      per-file MI -> mean over files
  SLOC    summed; comment % = total comments / total SLOC * 100
  Pylint  one run over all files together, overall score
  Bandit  findings summed by severity
Writes results/custom_metrics.csv.
"""
import argparse
import fnmatch
import json
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from statistics import mean

import pandas as pd
from radon.complexity import cc_visit
from radon.metrics import mi_visit
from radon.raw import analyze

from common import ROOT, RESULTS, read_selection, repo_dir

BIN = Path(sys.executable).parent
PYLINTRC = ROOT / "config" / "pylintrc"
PYLINT_TIMEOUT = 600
# same exclusions as the SonarQube scan, so both tools see the same files
EXCLUDE = ["*/node_modules/*", "*/.venv/*", "*/venv/*", "*/dist/*", "*/build/*",
           "*/target/*", "*/__pycache__/*", "*/site-packages/*"]


def python_files(path):
    out = subprocess.run(["git", "-C", str(path), "ls-files", "-z", "*.py"], check=True,
                         capture_output=True, text=True).stdout
    files = [f for f in out.split("\0") if f]
    kept = [f for f in files if not any(fnmatch.fnmatch("/" + f, p) for p in EXCLUDE)]
    return kept, len(files) - len(kept)


def radon_metrics(path, files):
    blocks, mis, sloc, comments, errors = [], [], 0, 0, 0
    for f in files:
        try:
            code = (path / f).read_text(encoding="utf-8", errors="replace")
            raw = analyze(code)
            items = cc_visit(code)
            mi = mi_visit(code, True)  # radon mi default: docstrings count as comments
        except Exception:
            errors += 1  # radon cannot parse it (e.g. Python 2 syntax)
            continue
        sloc += raw.sloc
        comments += raw.comments
        mis.append(mi)
        # cc_visit already lists functions, classes and methods separately, like `radon cc`
        blocks.extend(item.complexity for item in items)
    return {
        "py_cc_blocks": len(blocks),
        "py_cc_avg": round(mean(blocks), 4) if blocks else None,
        "py_cc_max": max(blocks) if blocks else None,
        "py_mi_avg": round(mean(mis), 4) if mis else None,
        "py_sloc": sloc,
        "py_comments": comments,
        "py_comment_pct": round(100 * comments / sloc, 4) if sloc else None,
        "py_parse_errors": errors,
    }


def run_pylint(path, files):
    # run from the repo root so relative paths work; the repo's own pylintrc is ignored
    proc = subprocess.run(
        [str(BIN / "pylint"), f"--rcfile={PYLINTRC}", "--reports=n", "--score=y",
         "--output-format=text", *files],
        cwd=path, capture_output=True, text=True, timeout=PYLINT_TIMEOUT)
    m = re.search(r"rated at (-?[\d.]+)/10", proc.stdout)
    fatal = sorted({line.split(":", 1)[0] for line in proc.stdout.splitlines()
                    if re.search(r":\d+:\d+: F\d{4}:", line)})
    if not m:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or [""]
        return None, fatal, f"pylint no score (exit {proc.returncode}): {tail[0][:150]}"
    return float(m.group(1)), fatal, ""


def pylint_score(path, files):
    """Pylint's own score, plus a rerun without files that raised a fatal message.

    Pylint's default evaluation gives 0 to the whole run if any file has a fatal
    message (e.g. a file it cannot parse), so both numbers are kept.
    """
    try:
        score, fatal, note = run_pylint(path, files)
        rest = [f for f in files if f not in fatal]
        if fatal and rest:
            excl, _, _ = run_pylint(path, rest)
            note = f"pylint fatal in {len(fatal)} file(s): {', '.join(fatal)[:150]}"
        else:
            excl = score
    except subprocess.TimeoutExpired:
        return None, None, 0, "pylint timeout"
    return score, excl, len(fatal), note


def bandit_counts(path, files):
    proc = subprocess.run([str(BIN / "bandit"), "-q", "-f", "json", *files],
                          cwd=path, capture_output=True, text=True)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"py_bandit_high": None, "py_bandit_medium": None, "py_bandit_low": None}, "bandit failed"
    sev = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for r in data.get("results", []):
        sev[r["issue_severity"]] = sev.get(r["issue_severity"], 0) + 1
    note = f"bandit skipped {len(data.get('errors', []))} file(s)" if data.get("errors") else ""
    return {"py_bandit_high": sev["HIGH"], "py_bandit_medium": sev["MEDIUM"],
            "py_bandit_low": sev["LOW"]}, note


def measure(item):
    org, repo, year = item
    path = repo_dir(year, repo)
    sha = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], check=True,
                         capture_output=True, text=True).stdout.strip()
    files, excluded = python_files(path)
    row = {"cohort_year": year, "org": org, "repo": repo, "commit_sha": sha,
           "python_file_count": len(files), "py_excluded_files": excluded}
    if not files:
        row["py_notes"] = "no tracked Python files"
        return row
    notes = []
    row.update(radon_metrics(path, files))
    (row["py_pylint_score"], row["py_pylint_score_excl_fatal"],
     row["py_pylint_fatal_files"], note) = pylint_score(path, files)
    notes.append(note)
    counts, note = bandit_counts(path, files)
    row.update(counts)
    notes.append(note)
    if row.get("py_parse_errors"):
        notes.append(f"radon could not parse {row['py_parse_errors']} file(s)")
    if excluded:
        notes.append(f"{excluded} vendored .py file(s) excluded")
    row["py_notes"] = "; ".join(n for n in notes if n)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="one repo name")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    items = read_selection()
    if args.only:
        items = [i for i in items if i[1] == args.only]
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(measure, items):
            print(f"{row['repo']}: {row['python_file_count']} py files, "
                  f"pylint={row.get('py_pylint_score')}", flush=True)
            rows.append(row)
    cols = ["cohort_year", "org", "repo", "commit_sha", "python_file_count", "py_excluded_files",
            "py_cc_blocks", "py_cc_avg", "py_cc_max", "py_mi_avg", "py_sloc", "py_comments",
            "py_comment_pct", "py_pylint_score", "py_pylint_score_excl_fatal",
            "py_pylint_fatal_files", "py_bandit_high", "py_bandit_medium",
            "py_bandit_low", "py_parse_errors", "py_notes"]
    df = pd.DataFrame(rows).reindex(columns=cols)
    out = RESULTS / "custom_metrics.csv"
    if args.only and out.exists():
        old = pd.read_csv(out)
        df = pd.concat([old[old.repo != args.only], df]).sort_values(["cohort_year", "repo"])
    df.to_csv(out, index=False)
    print(f"wrote results/custom_metrics.csv ({len(df)} rows)")


if __name__ == "__main__":
    main()
