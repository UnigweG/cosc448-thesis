# COSC 448 thesis - capstone repo metrics

Directed studies project (COSC 448, UBC Okanagan). The goal is to mine the COSC 499
capstone project repositories from three cohorts (GitHub orgs COSC-499-W2023,
COSC-499-W2024, COSC-499-W2025) and measure code quality with the metrics from my
supervisor's metrics document (docs/references/Metrics.pdf) plus SonarQube.

Deliverable 1 is the data pipeline: inventory the repos, pick the capstone projects,
clone them, and produce one metrics table per repo snapshot.

## Layout

    config/            repo_selection.txt (the repos used in every later step)
    scripts/           pipeline scripts, numbered in run order
    data/repos/<year>/ full clones (git-ignored)
    results/           CSV outputs
    docs/              metric definitions, SonarQube mapping, environment notes
    logs/              clone and scan logs (git-ignored)

## Setup

Needs git, gh (logged in with read access to the three orgs), jq, sonar-scanner and a
SonarQube server on localhost:9000.

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    cp .env.example .env     # then fill in SONAR_TOKEN (a SonarQube user token)

The scripts read .env themselves, so there is no need to export the token.

GitHub access is read only. Every clone gets its push URL set to DISABLED and a
pre-push hook that refuses to push.

## Running

    .venv/bin/python scripts/00_sonar_catalog.py      # SonarQube metric keys/languages -> docs/
    .venv/bin/python scripts/01_inventory.py          # all repos in the 3 orgs -> results/repo_inventory_all.csv
    .venv/bin/python scripts/01_inventory.py --groups # print name-pattern groups (add --examples for sample names)
    bash scripts/02_clone.sh                          # clone/fetch repos in config/repo_selection.txt
    .venv/bin/python scripts/02b_repo_stats.py        # commit stats -> results/repo_inventory.csv
    .venv/bin/python scripts/03_sonar_scan.py         # SonarQube scans -> results/sonar_scan_status.csv
    .venv/bin/python scripts/04_sonar_export.py       # SonarQube measures -> results/sonarqube_metrics.csv
    .venv/bin/python scripts/05_custom_metrics.py     # radon/pylint/bandit -> results/custom_metrics.csv
    .venv/bin/python scripts/06_build_results.py      # merged table -> results/results.csv

`03_sonar_scan.py` and `05_custom_metrics.py` also take `--only <repo>` to redo one repo.

Each script can be re-run; clones are fetched instead of re-cloned and SonarQube
projects are re-analysed in place.

## Notes

- docs/metrics_definitions.md - the metrics from the supervisor's document and how I compute them
- docs/metrics_mapping.md - which of them SonarQube 26.9 provides and which come from radon/pylint/bandit
- docs/metrics_notes.md - short explanations of each metric
- docs/results_schema.md - columns of results/results.csv
- docs/environment.md - tool versions
