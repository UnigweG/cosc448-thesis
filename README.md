# Code Quality in COSC 499 Capstone Repositories

COSC 448 Directed Studies, UBC Okanagan.
Gurkirn Kaur and Gabriel Unigwe, supervised under Dr. Bowen Hui

This project mines the COSC 499 capstone repositories from three cohorts and measures their code quality. The metrics come from the supervisor's metrics document ([`docs/references/Metrics.pdf`](docs/references/Metrics.pdf)), with SonarQube run alongside them. It also measures how the teams worked (repository evolution, review process, collaboration, development velocity) and looks for traces of AI coding tools, from the git history and the GitHub API.

| Cohort | GitHub organisation |
|--------|---------------------|
| 2023   | `COSC-499-W2023`    |
| 2024   | `COSC-499-W2024`    |
| 2025   | `COSC-499-W2025`    |

## Layout

    config/            repo_selection.txt (the repos used in every later step)
    scripts/           pipeline scripts, numbered in run order
    tests/             pytest suite (fixture repos, mocked SonarQube)
    data/repos/<year>/ full clones, with every PR head under refs/pull/ (git-ignored)
    data/github/<year>/ PRs, reviews and issues from the GitHub API (git-ignored)
    results/           CSV outputs
    docs/              metric definitions, SonarQube mapping (.md and .csv), environment notes
    logs/              clone and scan logs (git-ignored)

## Setup

### Prerequisites

- `git`
- GitHub CLI (`gh`), logged in with read access to all three organisations
- `sonar-scanner`
- A SonarQube server running on `localhost:9000`

### Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and fill in `SONAR_TOKEN`. It must be a SonarQube **user token**, not a global analysis token. The scripts load `.env` themselves, so you don't need to export anything.

`requirements.txt` pins every package, including transitive dependencies. That matters for packages like `astroid`, which is the parser Pylint uses. Everything in `results/` was produced with Python 3.14.0 and exactly these versions.

### GitHub access is read-only

Every clone has its push URL set to `DISABLED` and a pre-push hook that refuses to push.

---

## Running the pipeline

Run the scripts in this order:

```bash
.venv/bin/python scripts/00_sonar_catalog.py
.venv/bin/python scripts/01_inventory.py
bash scripts/02_clone.sh
.venv/bin/python scripts/02b_repo_stats.py
.venv/bin/python scripts/03_sonar_scan.py
.venv/bin/python scripts/04_sonar_export.py
.venv/bin/python scripts/05_custom_metrics.py
.venv/bin/python scripts/06_build_results.py
.venv/bin/python scripts/07_github_api.py
.venv/bin/python scripts/08_process_metrics.py
```

| Script                | What it does                                          | Output                                                                     |
|-----------------------|-------------------------------------------------------|----------------------------------------------------------------------------|
| `00_sonar_catalog.py` | Records the metric keys and languages SonarQube offers | `docs/sonarqube_metrics_available.csv`, `docs/sonarqube_languages.csv`     |
| `01_inventory.py`     | Lists every repo in the three organisations           | `results/repo_inventory_all.csv`                                           |
| `02_clone.sh`         | Clones or fetches the repos in `config/repo_selection.txt` | `data/repos/<year>/`                                                  |
| `02b_repo_stats.py`   | Collects commit statistics                            | `results/repo_inventory.csv`                                               |
| `03_sonar_scan.py`    | Runs a SonarQube scan on each repo                    | `results/sonar_scan_status.csv`                                            |
| `04_sonar_export.py`  | Exports SonarQube measures                            | `results/sonarqube_metrics.csv`                                            |
| `05_custom_metrics.py`| Runs Radon, Pylint and Bandit                         | `results/custom_metrics.csv`                                               |
| `06_build_results.py` | Merges everything into one table                      | `results/results.csv`                                                      |
| `07_github_api.py`    | Downloads PRs, reviews and issues from the GitHub API | `data/github/<year>/`                                                      |
| `08_process_metrics.py` | Team process metrics and AI-usage signals ([definitions](docs/process_metrics.md)) | `results/process_metrics.csv`, `results/ai_signals.csv` |

### Useful options

- `01_inventory.py --groups` prints the repo-name pattern groups. Add `--examples` to see sample names in each group.
- `03_sonar_scan.py`, `05_custom_metrics.py`, `07_github_api.py` and `08_process_metrics.py` take `--only <repo>` or `--only <org>/<repo>` to redo a single repo.
- `07_github_api.py` skips repos it has already saved; `--refresh` downloads them again.

### Re-running

Every script is safe to run again. Existing clones are fetched instead of re-cloned, and SonarQube projects are re-analysed in place.

A fetch does not move a clone's checked-out `HEAD`, so a re-run measures the same snapshot as the first run. To measure a different commit, check it out in `data/repos/<year>/<repo>` first.

### What each step depends on

- **`02b_repo_stats.py`** reads the clones and `results/repo_inventory_all.csv` from step 01. That CSV is git-ignored, so `results/results.csv` can't be rebuilt from the committed files alone.
- **`04_sonar_export.py`** reads from the SonarQube server, so the analyses from step 03 have to still be there.
- **`06_build_results.py`** reads the four result CSVs, plus the clones for snapshot dates.
- **`08_process_metrics.py`** reads the clones (including the PR heads that `02_clone.sh` fetches into `refs/pull/`), `data/github/` from step 07, and each repo's snapshot commit from `results/results.csv`. Its outputs hold aggregates only, no names or logins.

---

## Tests

```bash
.venv/bin/python -m pytest -q tests
```

The tests use small fixture repos and a mocked SonarQube API, so they need neither the clones nor a running server.

---