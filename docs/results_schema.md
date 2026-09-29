# `results/results.csv` Schema

Each row is one **snapshot**: one repository at one commit. The key is `(org, repo, commit_sha)`.

- **D1** has one snapshot per repo: the `HEAD` of the default branch at the time of cloning.
- **D3** can append more rows for older commits of the same repos. `scripts/06_build_results.py` keeps existing rows with other commit SHAs and only replaces rows with the same key.

The file is built by `scripts/06_build_results.py` from four inputs:

- `repo_inventory.csv`
- `sonarqube_metrics.csv`
- `sonar_scan_status.csv`
- `custom_metrics.csv`

It contains only repo names and metrics. There are no student names or emails.

## Contents

- [Identification](#identification)
- [SonarQube columns (`sq_*`)](#sonarqube-columns-sq_)
- [Python metrics (`py_*`)](#python-metrics-py_)
- [Adding snapshots later (D3)](#adding-snapshots-later-d3)

---

## Identification

| Column | Type | Meaning |
|---|---|---|
| `cohort_year` | int | 2023, 2024 or 2025 (from the org name) |
| `org` | str | GitHub organisation, e.g. `COSC-499-W2024` |
| `repo` | str | Repository name |
| `section` | str | Course section (`002` or `003`) if it appears in the repo name or description, otherwise blank |
| `team_key` | str | Best-effort team ID in the form `<year>-t<number>[-<section>]`, used to spot duplicate repos for the same team |
| `commit_sha` | str | The analysed commit |
| `snapshot_date` | ISO datetime | Committer date of `commit_sha` |

---

## SonarQube columns (`sq_*`)

These come from SonarQube 26.9 Community, via `scripts/04_sonar_export.py`.

> Project-level measures cover **all analysed languages**, unless the column name starts with `sq_py_`.

### Scan info

| Column | SonarQube key / formula | Notes |
|---|---|---|
| `sq_scan_status`, `sq_scan_notes` | from `sonar_scan_status.csv` | `ok`, `failed` or `pending` (the server queue timed out and the task wasn't checked), plus language warnings |
| `sq_analysis_date` | `/api/project_analyses/search` | When the analysis ran, not the commit date |

### Size and comments

| Column | SonarQube key / formula | Notes |
|---|---|---|
| `sq_ncloc`, `sq_lines`, `sq_statements`, `sq_functions`, `sq_classes`, `sq_files` | same keys | Size |
| `sq_comment_lines` | `comment_lines` | |
| `sq_comment_lines_density` | `comment_lines_density` | `comment_lines / (ncloc + comment_lines) * 100` |
| `sq_comment_pct_pdf` | derived | `comment_lines / ncloc * 100` (PDF formula on SonarQube counts) |
| `sq_ncloc_language_distribution` | `ncloc_language_distribution` | e.g. `js=2131;py=7298` |

### Complexity and duplication

| Column | SonarQube key / formula | Notes |
|---|---|---|
| `sq_complexity` | `complexity` | Cyclomatic total |
| `sq_complexity_per_function` | derived | `complexity / functions` (rough; not the PDF's CCavg) |
| `sq_cognitive_complexity` | `cognitive_complexity` | |
| `sq_duplicated_lines_density`, `sq_duplicated_blocks` | same keys | |

### Issues and ratings

| Column | SonarQube key / formula | Notes |
|---|---|---|
| `sq_bugs`, `sq_vulnerabilities`, `sq_code_smells`, `sq_security_hotspots`, `sq_violations` | same keys | |
| `sq_issues_per_kloc` | derived | `violations / ncloc * 1000` (rough Pylint proxy) |
| `sq_sqale_index` | `sqale_index` | Technical debt in minutes |
| `sq_sqale_debt_ratio`, `sq_sqale_rating` | same keys | Rating: 1 = A ... 5 = E |
| `sq_reliability_rating`, `sq_security_rating` | same keys | 1 = A ... 5 = E |
| `sq_software_quality_*_issues` | same keys | Issue counts by quality (maintainability / reliability / security) and by impact severity (blocker / high / medium / low / info) |
| `sq_software_quality_maintainability_rating`, `sq_software_quality_maintainability_debt_ratio` | same keys | |
| `sq_issues_sev_{blocker,critical,major,minor,info}` | `/api/issues/search`, facet `severities` | Open issues only |
| `sq_issues_impact_{blocker,high,medium,low,info}` | facet `impactSeverities` | Open issues only |

### Python only (`sq_py_*`)

| Column | SonarQube key / formula | Notes |
|---|---|---|
| `sq_py_files`, `sq_py_ncloc`, `sq_py_comment_lines`, `sq_py_complexity`, `sq_py_functions`, `sq_py_classes` | Sum of per-file measures where `language = py` | Python only; comparable with Radon |
| `sq_py_file_complexity_max` | Max per-file `complexity` over Python files | Not the same as CCmax |
| `sq_py_comment_pct_pdf` | derived | `sq_py_comment_lines / sq_py_ncloc * 100` |

---

## Python metrics (`py_*`)

These are the supervisor's metrics, from `scripts/05_custom_metrics.py`, using Radon 6.0.1, Pylint 4.0.9 and Bandit 1.9.4. They run on `git ls-files '*.py'` minus vendored paths, and are `NA` when `python_file_count = 0`.

| Column | Meaning |
|---|---|
| `python_file_count` | Tracked `.py` files analysed |
| `py_excluded_files` | Tracked `.py` files skipped as vendored (`venv`, `site-packages`, `node_modules`, ...) |
| `py_cc_blocks` | Number of functions / methods / classes pooled |
| `py_cc_avg` | CCavg: mean CC over the pooled blocks |
| `py_cc_max` | CCmax: max CC over the pooled blocks |
| `py_mi_avg` | MI: mean of the per-file maintainability index |
| `py_sloc` | SLOC, summed |
| `py_comments` | Comment lines, summed |
| `py_comment_pct` | `py_comments / py_sloc * 100` |
| `py_pylint_score` | Pylint score out of 10, from one run over all files with 4 import checks disabled (`config/pylintrc`) |
| `py_pylint_score_excl_fatal` | Pylint score re-run without the files that raised a fatal message (same as `py_pylint_score` when there were none) |
| `py_pylint_fatal_files` | Number of files with a fatal Pylint message (these force Pylint's own score to 0) |
| `py_bandit_high`, `py_bandit_medium`, `py_bandit_low` | Bandit findings by severity, summed |
| `py_parse_errors` | Files Radon couldn't parse (left out of the Radon metrics) |
| `py_notes` | Failures, timeouts and exclusions |

---

## Adding snapshots later (D3)

1. Check out the target commit in a separate worktree under `data/`.
2. Run the same tools on it. SonarQube needs a separate project key or project version for each snapshot; otherwise each analysis replaces the previous one in the project overview.
3. Append rows with the new `commit_sha` and `snapshot_date`.

The deltas in [`metrics_definitions.md`](metrics_definitions.md) are then just differences between two rows of the same repo (or `team_key`).
